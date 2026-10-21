"""Unit tests for ByteTrack multi-object tracker and PPE head/torso association."""

from __future__ import annotations

import numpy as np
from fieldkit_vision.detector import Detection
from fieldkit_vision.tracker import (
    ByteTracker,
    TrackedEntity,
    TrackState,
    associate_ppe_to_tracks,
    box_iou,
)


def test_box_iou() -> None:
    """Verify standard axis-aligned bounding box Intersection over Union."""
    box_a = np.array([100.0, 100.0, 200.0, 200.0])  # Area 10,000
    box_b = np.array([150.0, 100.0, 250.0, 200.0])  # Area 10,000, Overlap: 50x100 = 5,000
    # Union = 10,000 + 10,000 - 5,000 = 15,000 -> IoU = 5,000 / 15,000 = 0.3333
    iou = box_iou(box_a, box_b)
    assert round(iou, 4) == round(1 / 3, 4)

    # Disjoint boxes
    box_c = np.array([300.0, 300.0, 400.0, 400.0])
    assert box_iou(box_a, box_c) == 0.0


def test_bytetrack_trajectory_and_lifecycle() -> None:
    """Verify track initiation, ID persistence, motion prediction, and removal."""
    tracker = ByteTracker(
        camera_id="cam1_press",
        track_thresh=0.5,
        low_thresh=0.1,
        match_thresh=0.7,
        max_time_lost=5,
    )

    # Frame 1: Person walking across the frame at x=100
    det_f1 = [
        Detection(box=[100.0, 200.0, 200.0, 500.0], class_id=0, class_name="person", confidence=0.92)
    ]
    tracks_f1 = tracker.update(det_f1, timestamp=1.0)
    assert len(tracks_f1) == 1
    t1 = tracks_f1[0]
    track_id = t1.track_id
    assert t1.class_name == "person"
    assert t1.state == TrackState.Tracked
    assert t1.foot_point == (150.0, 500.0)

    # Frame 2: Person moves to x=115 (velocity ~ 15 px/frame)
    det_f2 = [
        Detection(box=[115.0, 200.0, 215.0, 500.0], class_id=0, class_name="person", confidence=0.88)
    ]
    tracks_f2 = tracker.update(det_f2, timestamp=1.2)
    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == track_id  # ID must persist
    assert round(tracks_f2[0].box[0]) == 115

    # Frame 3: Low-confidence detection (occlusion / blur: conf=0.25)
    det_f3 = [
        Detection(box=[130.0, 200.0, 230.0, 500.0], class_id=0, class_name="person", confidence=0.25)
    ]
    tracks_f3 = tracker.update(det_f3, timestamp=1.4)
    assert len(tracks_f3) == 1
    assert tracks_f3[0].track_id == track_id  # Successfully recovered via 2nd-stage ByteTrack

    # Frame 4: Missing detection (person temporarily hidden)
    tracks_f4 = tracker.update([], timestamp=1.6)
    # Active tracks returned should be empty, but track is kept in 'lost' pool
    assert len(tracks_f4) == 0
    assert track_id in tracker.lost_tracks

    # Frame 5: Re-emergence at predicted position x=160
    det_f5 = [
        Detection(box=[160.0, 200.0, 260.0, 500.0], class_id=0, class_name="person", confidence=0.85)
    ]
    tracks_f5 = tracker.update(det_f5, timestamp=1.8)
    assert len(tracks_f5) == 1
    assert tracks_f5[0].track_id == track_id  # Track recovered from lost pool!


def test_head_region_ppe_association() -> None:
    """Verify that helmets and vests are correctly assigned to tracked persons."""
    # Person at [200, 100, 300, 500] (w=100, h=400)
    # Head region is top 25%: [200, 100, 300, 200]
    person_track = TrackedEntity(
        track_id=1,
        camera_id="cam1",
        class_id=0,
        class_name="person",
        box=[200.0, 100.0, 300.0, 500.0],
        confidence=0.95,
    )

    # Detections in frame: 1 hardhat on head, 1 vest on torso, 1 disjoint hardhat elsewhere
    detections = [
        # Hardhat located on person's head: [210, 105, 290, 160]
        Detection(box=[210.0, 105.0, 290.0, 160.0], class_id=1, class_name="helmet", confidence=0.91),
        # Safety vest located on person's torso: [210, 200, 290, 350]
        Detection(box=[210.0, 200.0, 290.0, 350.0], class_id=3, class_name="vest", confidence=0.93),
        # Disjoint hardhat on ground elsewhere: [800, 800, 850, 850]
        Detection(box=[800.0, 800.0, 850.0, 850.0], class_id=1, class_name="helmet", confidence=0.85),
    ]

    associate_ppe_to_tracks([person_track], detections)

    assert person_track.is_wearing_helmet is True
    assert person_track.is_wearing_vest is True
    assert person_track.helmet_confidence >= 0.90
    assert person_track.vest_confidence >= 0.90


def test_no_helmet_and_rolling_compliance_window() -> None:
    """Verify temporal smoothing over rolling window avoids single-frame alert flapping."""
    person_track = TrackedEntity(
        track_id=2,
        camera_id="cam1",
        class_id=0,
        class_name="person",
        box=[200.0, 100.0, 300.0, 500.0],
        confidence=0.95,
        window_size=10,
    )

    # Step 1: 8 frames of wearing helmet
    helmet_det = [
        Detection(box=[210.0, 105.0, 290.0, 160.0], class_id=1, class_name="helmet", confidence=0.90)
    ]
    for _ in range(8):
        associate_ppe_to_tracks([person_track], helmet_det)

    assert person_track.helmet_compliance_ratio == 1.0
    assert person_track.is_wearing_helmet is True

    # Step 2: 1 frame of momentary detector flicker / missed head
    associate_ppe_to_tracks([person_track], [])
    # 8 compliant out of 9 total observations -> ratio = 8/9 = 0.8889
    assert person_track.helmet_compliance_ratio > 0.85
    # Smoothed state remains compliant
    assert person_track.is_wearing_helmet is True

    # Step 3: Explicit no_helmet detected across 7 consecutive frames
    no_helmet_det = [
        Detection(box=[210.0, 105.0, 290.0, 160.0], class_id=2, class_name="no_helmet", confidence=0.92)
    ]
    for _ in range(7):
        associate_ppe_to_tracks([person_track], no_helmet_det)

    # Rolling window (size 10) now has mostly no_helmet detections
    assert person_track.helmet_compliance_ratio < 0.30
    assert person_track.is_wearing_helmet is False
