"""ByteTrack multi-object tracker, motion prediction, and PPE head/torso association."""

from __future__ import annotations

import logging
from collections import deque
from enum import Enum

import numpy as np
from scipy.optimize import linear_sum_assignment

from fieldkit_vision.detector import Detection

logger = logging.getLogger("fieldkit.vision.tracker")


class TrackState(int, Enum):
    """Lifecycle state machine for tracked objects."""

    New = 0
    Tracked = 1
    Lost = 2
    Removed = 3


def box_iou(box_a: np.ndarray | list[float], box_b: np.ndarray | list[float]) -> float:
    """Compute Intersection-over-Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b

    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
    area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


def batch_box_iou(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Compute IoU cost matrix between N boxes and M boxes."""
    if len(boxes_a) == 0 or len(boxes_b) == 0:
        return np.empty((len(boxes_a), len(boxes_b)), dtype=np.float64)

    ious = np.zeros((len(boxes_a), len(boxes_b)), dtype=np.float64)
    for i, ba in enumerate(boxes_a):
        for j, bb in enumerate(boxes_b):
            ious[i, j] = box_iou(ba, bb)
    return ious


class TrackedEntity:
    """Tracked object entity with Kalman motion prediction, trajectory, and PPE observation history."""

    def __init__(
        self,
        track_id: int,
        camera_id: str,
        class_id: int,
        class_name: str,
        box: list[float],
        confidence: float,
        timestamp: float = 0.0,
        window_size: int = 10,
    ) -> None:
        self.track_id = track_id
        self.camera_id = camera_id
        self.class_id = class_id
        self.class_name = class_name
        self.box = [float(c) for c in box]
        self.confidence = float(confidence)
        self.state = TrackState.Tracked
        self.timestamp = timestamp

        # Motion and velocity (dx, dy in pixels/sec)
        self.velocity = (0.0, 0.0)
        self.speed_mps = 0.0
        self.floor_coord: tuple[float, float] | None = None

        # Trajectory of bottom-center foot points: (timestamp, x, y)
        self.trajectory: deque[tuple[float, float, float]] = deque(maxlen=60)
        self.trajectory.append((timestamp, self.foot_point[0], self.foot_point[1]))

        # Track history counts
        self.hits = 1
        self.lost_frames = 0
        self.age = 1

        # PPE Observation Histories (rolling window of observations)
        self.window_size = window_size
        self.helmet_history: deque[bool | None] = deque(maxlen=window_size)
        self.vest_history: deque[bool | None] = deque(maxlen=window_size)
        self.helmet_confidence: float = 0.0
        self.vest_confidence: float = 0.0
        self.is_wearing_helmet: bool = False
        self.is_wearing_vest: bool = False

    @property
    def width(self) -> float:
        return max(0.0, self.box[2] - self.box[0])

    @property
    def height(self) -> float:
        return max(0.0, self.box[3] - self.box[1])

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0

    @property
    def foot_point(self) -> tuple[float, float]:
        """Bottom-center foot contact point on floor plane (x_c, y2)."""
        return (self.box[0] + self.box[2]) / 2.0, self.box[3]

    @property
    def head_region(self) -> list[float]:
        """Top 25% region of the person bounding box for hardhat association."""
        return [
            self.box[0],
            self.box[1],
            self.box[2],
            self.box[1] + 0.25 * self.height,
        ]

    @property
    def torso_region(self) -> list[float]:
        """Middle torso region for high-visibility vest association."""
        return [
            self.box[0],
            self.box[1] + 0.20 * self.height,
            self.box[2],
            self.box[1] + 0.75 * self.height,
        ]

    @property
    def helmet_compliance_ratio(self) -> float:
        """Proportion of positive helmet observations in rolling window."""
        valid_obs = [o for o in self.helmet_history if o is not None]
        if not valid_obs:
            return 1.0 if self.is_wearing_helmet else 0.0
        return sum(1 for o in valid_obs if o) / len(valid_obs)

    @property
    def vest_compliance_ratio(self) -> float:
        """Proportion of positive safety vest observations in rolling window."""
        valid_obs = [o for o in self.vest_history if o is not None]
        if not valid_obs:
            return 1.0 if self.is_wearing_vest else 0.0
        return sum(1 for o in valid_obs if o) / len(valid_obs)

    def predict(self) -> list[float]:
        """Predict bounding box at next time step based on linear motion."""
        vx, vy = self.velocity
        pred_box = [
            self.box[0] + vx,
            self.box[1] + vy,
            self.box[2] + vx,
            self.box[3] + vy,
        ]
        return pred_box

    def update_detection(self, detection: Detection, timestamp: float) -> None:
        """Update track with matched detection and update velocity estimate."""
        prev_cx, prev_cy = self.center

        # Update box and confidence
        self.box = [float(c) for c in detection.box]
        self.confidence = float(detection.confidence)
        self.timestamp = timestamp

        new_cx, new_cy = self.center
        # Exponential smoothing on velocity: alpha=0.7
        inst_vx = (new_cx - prev_cx)
        inst_vy = (new_cy - prev_cy)
        self.velocity = (
            0.7 * inst_vx + 0.3 * self.velocity[0],
            0.7 * inst_vy + 0.3 * self.velocity[1],
        )

        self.trajectory.append((timestamp, self.foot_point[0], self.foot_point[1]))
        self.hits += 1
        self.lost_frames = 0
        self.state = TrackState.Tracked
        self.age += 1

    def mark_lost(self) -> None:
        """Mark track as lost (occluded or temporarily missed by detector)."""
        self.lost_frames += 1
        self.state = TrackState.Lost
        self.age += 1
        # Advance position by predicted velocity
        vx, vy = self.velocity
        self.box = [
            self.box[0] + vx,
            self.box[1] + vy,
            self.box[2] + vx,
            self.box[3] + vy,
        ]

    def add_helmet_observation(self, observed: bool | None, confidence: float = 0.0) -> None:
        """Record an observation of helmet presence in rolling window."""
        self.helmet_history.append(observed)
        if observed is True:
            self.helmet_confidence = confidence
        elif observed is False:
            self.helmet_confidence = 1.0 - confidence

        # Update smoothed state: compliant if compliance ratio >= 0.50
        self.is_wearing_helmet = self.helmet_compliance_ratio >= 0.50

    def add_vest_observation(self, observed: bool | None, confidence: float = 0.0) -> None:
        """Record an observation of safety vest presence in rolling window."""
        self.vest_history.append(observed)
        if observed is True:
            self.vest_confidence = confidence
        elif observed is False:
            self.vest_confidence = 1.0 - confidence

        self.is_wearing_vest = self.vest_compliance_ratio >= 0.50


class ByteTracker:
    """ByteTrack two-stage data association multi-object tracker."""

    def __init__(
        self,
        camera_id: str,
        track_thresh: float = 0.5,
        low_thresh: float = 0.1,
        match_thresh: float = 0.7,
        max_time_lost: int = 30,
    ) -> None:
        self.camera_id = camera_id
        self.track_thresh = track_thresh
        self.low_thresh = low_thresh
        self.match_thresh = match_thresh
        self.max_time_lost = max_time_lost

        self._next_id: int = 1
        self.tracked_tracks: dict[int, TrackedEntity] = {}
        self.lost_tracks: dict[int, TrackedEntity] = {}
        self.removed_tracks: dict[int, TrackedEntity] = {}

    def update(self, detections: list[Detection], timestamp: float = 0.0) -> list[TrackedEntity]:
        """Update tracker with frame detections using ByteTrack two-stage association."""
        # Only track person and forklift classes (helmets/vests are associated via PPE assigner)
        trackable_dets = [d for d in detections if d.class_name in ("person", "forklift")]

        # Split into high-confidence and low-confidence detections
        dets_high = [d for d in trackable_dets if d.confidence >= self.track_thresh]
        dets_low = [d for d in trackable_dets if self.low_thresh <= d.confidence < self.track_thresh]

        # Candidate tracks: currently tracked + lost tracks
        candidate_tracks = list(self.tracked_tracks.values()) + list(self.lost_tracks.values())

        # Step 1: Predict candidate tracks forward
        for track in candidate_tracks:
            track.predict()

        # Step 2: First association (dets_high with candidate_tracks)
        matched_tracks_1: set[int] = set()
        matched_dets_1: set[int] = set()

        if candidate_tracks and dets_high:
            track_boxes = np.array([t.box for t in candidate_tracks])
            det_boxes = np.array([d.box for d in dets_high])
            iou_matrix = batch_box_iou(track_boxes, det_boxes)

            # Cost matrix: 1 - IoU
            cost_matrix = 1.0 - iou_matrix
            row_inds, col_inds = linear_sum_assignment(cost_matrix)

            for r, c in zip(row_inds, col_inds, strict=False):
                # IoU must be >= (1.0 - match_thresh), e.g. >= 0.3
                if cost_matrix[r, c] <= self.match_thresh:
                    track = candidate_tracks[r]
                    det = dets_high[c]
                    track.update_detection(det, timestamp)
                    matched_tracks_1.add(track.track_id)
                    matched_dets_1.add(c)
                    # Restore from lost if previously lost
                    if track.track_id in self.lost_tracks:
                        del self.lost_tracks[track.track_id]
                        self.tracked_tracks[track.track_id] = track

        # Remaining active tracks that were not matched
        remaining_active_tracks = [
            t for t in self.tracked_tracks.values() if t.track_id not in matched_tracks_1
        ]

        # Step 3: Second association (dets_low with remaining_active_tracks)
        matched_tracks_2: set[int] = set()
        matched_dets_2: set[int] = set()

        if remaining_active_tracks and dets_low:
            track_boxes = np.array([t.box for t in remaining_active_tracks])
            det_boxes = np.array([d.box for d in dets_low])
            iou_matrix = batch_box_iou(track_boxes, det_boxes)
            cost_matrix = 1.0 - iou_matrix

            row_inds, col_inds = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_inds, col_inds, strict=False):
                # Lower confidence detections require solid IoU overlap (cost <= 0.6 -> IoU >= 0.4)
                if cost_matrix[r, c] <= 0.6:
                    track = remaining_active_tracks[r]
                    det = dets_low[c]
                    track.update_detection(det, timestamp)
                    matched_tracks_2.add(track.track_id)
                    matched_dets_2.add(c)

        # Step 4: Handle unmatched tracks -> move to Lost or Removed
        all_matched_ids = matched_tracks_1 | matched_tracks_2
        for t_id, track in list(self.tracked_tracks.items()):
            if t_id not in all_matched_ids:
                track.mark_lost()
                del self.tracked_tracks[t_id]
                self.lost_tracks[t_id] = track

        for t_id, track in list(self.lost_tracks.items()):
            if t_id not in all_matched_ids:
                track.lost_frames += 1
                if track.lost_frames > self.max_time_lost:
                    track.state = TrackState.Removed
                    del self.lost_tracks[t_id]
                    self.removed_tracks[t_id] = track

        # Step 5: Unmatched high-confidence detections initiate new tracks
        for i, det in enumerate(dets_high):
            if i not in matched_dets_1:
                new_track = TrackedEntity(
                    track_id=self._next_id,
                    camera_id=self.camera_id,
                    class_id=det.class_id,
                    class_name=det.class_name,
                    box=det.box,
                    confidence=det.confidence,
                    timestamp=timestamp,
                )
                self.tracked_tracks[new_track.track_id] = new_track
                self._next_id += 1

        # Return list of actively tracked entities
        return list(self.tracked_tracks.values())


def associate_ppe_to_tracks(person_tracks: list[TrackedEntity], detections: list[Detection]) -> None:
    """Associate helmet, no_helmet, and vest detections to tracked persons via head and torso overlap."""
    helmets = [d for d in detections if d.class_name == "helmet"]
    no_helmets = [d for d in detections if d.class_name == "no_helmet"]
    vests = [d for d in detections if d.class_name == "vest"]

    for person in person_tracks:
        if person.class_name != "person":
            continue

        head_box = person.head_region
        torso_box = person.torso_region

        # 1. Helmet / No-Helmet Association
        best_head_det: Detection | None = None
        best_head_iou: float = 0.0

        for h_det in helmets + no_helmets:
            # Overlap between detection and person head region
            iou = box_iou(head_box, h_det.box)
            # Center inclusion check with fallback
            cx = (h_det.box[0] + h_det.box[2]) / 2.0
            cy = (h_det.box[1] + h_det.box[3]) / 2.0
            in_head = (
                person.box[0] - 0.1 * person.width <= cx <= person.box[2] + 0.1 * person.width
                and person.box[1] - 0.1 * person.height <= cy <= person.box[1] + 0.35 * person.height
            )

            score = iou if iou > 0.1 else (0.35 if in_head else 0.0)
            if score > best_head_iou:
                best_head_iou = score
                best_head_det = h_det

        if best_head_det is not None and best_head_iou >= 0.10:
            if best_head_det.class_name == "helmet":
                person.add_helmet_observation(True, confidence=best_head_det.confidence)
            else:
                person.add_helmet_observation(False, confidence=best_head_det.confidence)
        else:
            # No clear head observation in this frame
            person.add_helmet_observation(None, confidence=0.0)

        # 2. Vest Association
        best_vest_det: Detection | None = None
        best_vest_iou: float = 0.0

        for v_det in vests:
            iou = box_iou(torso_box, v_det.box)
            cx = (v_det.box[0] + v_det.box[2]) / 2.0
            cy = (v_det.box[1] + v_det.box[3]) / 2.0
            in_torso = (
                person.box[0] - 0.1 * person.width <= cx <= person.box[2] + 0.1 * person.width
                and person.box[1] + 0.15 * person.height <= cy <= person.box[1] + 0.80 * person.height
            )

            score = iou if iou > 0.1 else (0.40 if in_torso else 0.0)
            if score > best_vest_iou:
                best_vest_iou = score
                best_vest_det = v_det

        if best_vest_det is not None and best_vest_iou >= 0.10:
            person.add_vest_observation(True, confidence=best_vest_det.confidence)
        else:
            person.add_vest_observation(False, confidence=0.0)
