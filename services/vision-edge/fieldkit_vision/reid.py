"""Cross-Camera Person Re-Identification (Re-ID) and Spatial-Temporal Topology Engine.

Implements person crop extraction, sharpness-weighted sampling, OSNet feature embedding,
L2 normalization, cosine similarity matching, and spatial-temporal transit topology gating
to track workers across disconnected cameras without cloud APIs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from pydantic import BaseModel, Field


class CameraTransition(BaseModel):
    """Pairwise camera transition constraint."""

    from_camera: str
    to_camera: str
    min_transit_time_sec: float = Field(default=3.0, ge=0.0)
    max_transit_time_sec: float = Field(default=60.0, ge=0.0)
    default_distance_meters: float = Field(default=15.0, ge=0.0)


class CameraTopology(BaseModel):
    """Plant camera spatial graph topology defining allowed transitions."""

    plant_id: str = "DE-HAM"
    cameras: list[dict[str, Any]] = Field(default_factory=list)
    transitions: list[CameraTransition] = Field(default_factory=list)
    similarity_threshold: float = 0.75

    @classmethod
    def from_yaml(cls, path: str | Path) -> CameraTopology:
        """Load topology configuration from YAML."""
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        reid_cfg = data.get("reid_thresholds", {})
        thresh = float(reid_cfg.get("cosine_similarity_min", 0.75))

        transitions = [
            CameraTransition(
                from_camera=t["from_camera"],
                to_camera=t["to_camera"],
                min_transit_time_sec=float(t.get("min_transit_time_sec", 3.0)),
                max_transit_time_sec=float(t.get("max_transit_time_sec", 60.0)),
                default_distance_meters=float(t.get("default_distance_meters", 15.0)),
            )
            for t in data.get("transitions", [])
        ]

        return cls(
            plant_id=data.get("plant_id", "DE-HAM"),
            cameras=data.get("cameras", []),
            transitions=transitions,
            similarity_threshold=thresh,
        )

    def get_transition(self, from_camera: str, to_camera: str) -> CameraTransition | None:
        """Find transition definition between two cameras."""
        for t in self.transitions:
            if t.from_camera == from_camera and t.to_camera == to_camera:
                return t
        return None

    def is_transit_valid(self, from_camera: str, to_camera: str, elapsed_sec: float) -> bool:
        """Validate if the elapsed transit time satisfies the physical spatial transition."""
        transition = self.get_transition(from_camera, to_camera)
        if not transition:
            return False
        return transition.min_transit_time_sec <= elapsed_sec <= transition.max_transit_time_sec


@dataclass
class PersonCrop:
    """Cropped person entity with image data and quality metric."""

    crop_image: np.ndarray
    track_id: int
    timestamp: float
    area: int
    sharpness: float


def extract_person_crop(
    image: np.ndarray,
    box: Sequence[float],
    track_id: int,
    timestamp: float,
    min_area: int = 2500,
) -> PersonCrop | None:
    """Extract a person bounding box crop from an image and compute its sharpness."""
    if image is None or image.size == 0 or len(box) < 4:
        return None

    h, w = image.shape[:2]
    x1 = max(0, min(int(box[0]), w - 1))
    y1 = max(0, min(int(box[1]), h - 1))
    x2 = max(0, min(int(box[2]), w))
    y2 = max(0, min(int(box[3]), h))

    crop_w = x2 - x1
    crop_h = y2 - y1
    area = crop_w * crop_h

    if area < min_area or crop_w <= 0 or crop_h <= 0:
        return None

    crop = image[y1:y2, x1:x2]

    # Compute sharpness using Laplacian variance
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    return PersonCrop(
        crop_image=crop,
        track_id=track_id,
        timestamp=timestamp,
        area=area,
        sharpness=sharpness,
    )


def compute_cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two feature vectors."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-8 or norm2 < 1e-8:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


class OSNetFeatureExtractor:
    """Extracts 512-dimensional L2-normalized feature embeddings from person crops.

    Supports ONNX runtime execution with local deterministic fallback when the
    model weight file is not yet deployed.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path else None
        self._session: Any = None
        if self.model_path and self.model_path.exists():
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(
                    str(self.model_path),
                    providers=["CPUExecutionProvider"],
                )
            except Exception:
                self._session = None

    def extract(self, crop: np.ndarray) -> np.ndarray:
        """Extract a 512-dimensional normalized feature embedding for a person crop."""
        if crop is None or crop.size == 0:
            v = np.zeros(512, dtype=np.float32)
            v[0] = 1.0
            return v

        # Standard OSNet input shape: (256, 128)
        resized = cv2.resize(crop, (128, 256), interpolation=cv2.INTER_LINEAR)

        if self._session is not None:
            # Normalize with ImageNet mean and std
            norm_img = resized.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            norm_img = (norm_img - mean) / std
            # Transpose to NCHW
            tensor = np.transpose(norm_img, (2, 0, 1))[np.newaxis, ...]

            input_name = self._session.get_inputs()[0].name
            raw_out = self._session.run(None, {input_name: tensor})[0]
            emb = raw_out.flatten().astype(np.float32)
        else:
            # Deterministic multi-scale texture & color feature representation for local testing
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
            h_hist = cv2.calcHist([hsv], [0], None, [64], [0, 180]).flatten()
            s_hist = cv2.calcHist([hsv], [1], None, [64], [0, 256]).flatten()
            v_hist = cv2.calcHist([hsv], [2], None, [64], [0, 256]).flatten()

            # Upper and lower body split histograms
            upper = resized[:128, :]
            lower = resized[128:, :]
            upper_hist = cv2.calcHist([upper], [0, 1, 2], None, [5, 5, 5], [0, 256, 0, 256, 0, 256]).flatten()
            lower_hist = cv2.calcHist([lower], [0, 1, 2], None, [5, 5, 5], [0, 256, 0, 256, 0, 256]).flatten()

            combined = np.concatenate([h_hist, s_hist, v_hist, upper_hist, lower_hist])
            # Pad or slice to exactly 512 dimensions
            if len(combined) < 512:
                emb = np.pad(combined, (0, 512 - len(combined)))
            else:
                emb = combined[:512]
            emb = emb.astype(np.float32)

        # L2 normalization
        norm = np.linalg.norm(emb)
        if norm > 1e-8:
            emb /= norm
        else:
            emb[0] = 1.0

        res_emb: np.ndarray = np.asarray(emb, dtype=np.float32)
        return res_emb


@dataclass
class PersonTrackEmbedding:
    """Accumulated Re-ID feature embedding for a local camera track."""

    camera_id: str
    track_id: int
    first_seen: float
    last_seen: float
    embedding: np.ndarray
    crop_count: int = 1

    def update_with_crop(self, crop_emb: np.ndarray, timestamp: float, weight: float = 1.0) -> None:
        """Update track embedding with a new crop observation using weighted moving average."""
        self.last_seen = max(self.last_seen, timestamp)
        self.crop_count += 1
        # Weighted accumulation
        self.embedding = self.embedding + (crop_emb * weight)
        # Re-normalize
        norm = np.linalg.norm(self.embedding)
        if norm > 1e-8:
            self.embedding /= norm


@dataclass
class PersonSighting:
    """Record of a person sighting at a specific camera."""

    global_person_id: str
    camera_id: str
    track_id: int
    first_seen: float
    last_seen: float
    similarity: float = 1.0


class GlobalPersonRegistry:
    """Cross-camera global identity tracker and journey reconstructor."""

    def __init__(
        self,
        topology: CameraTopology | None = None,
        similarity_threshold: float = 0.75,
        max_history_sec: float = 1800.0,
    ) -> None:
        self.topology = topology or CameraTopology()
        self.similarity_threshold = similarity_threshold
        self.max_history_sec = max_history_sec
        self._next_id = 1
        self._active_tracks: dict[tuple[str, int], PersonTrackEmbedding] = {}
        self._track_to_global_id: dict[tuple[str, int], str] = {}
        self._journeys: dict[str, list[PersonSighting]] = {}

    def register_or_match(self, track: PersonTrackEmbedding) -> str:
        """Match new local camera tracklet against past sightings across the plant.

        Enforces cosine similarity threshold and spatial-temporal transit topology.
        """
        key = (track.camera_id, track.track_id)
        if key in self._track_to_global_id:
            # Already matched, update track
            self._active_tracks[key] = track
            return self._track_to_global_id[key]

        best_match_id: str | None = None
        best_similarity = -1.0

        # Scan active tracks for cross-camera match candidates
        for (cand_cam, cand_tid), cand_track in self._active_tracks.items():
            if cand_cam == track.camera_id:
                # Same camera, distinct tracks are handled by local tracker
                continue

            elapsed = track.first_seen - cand_track.last_seen
            if elapsed < 0:
                # Candidate sighting occurred in the future relative to track start
                continue

            # Verify transit feasibility in topology
            if not self.topology.is_transit_valid(cand_cam, track.camera_id, elapsed):
                continue

            # Compute similarity
            sim = compute_cosine_similarity(track.embedding, cand_track.embedding)
            if sim >= self.similarity_threshold and sim > best_similarity:
                best_similarity = sim
                best_match_id = self._track_to_global_id.get((cand_cam, cand_tid))

        if best_match_id is not None:
            global_id = best_match_id
        else:
            global_id = f"person_{self._next_id:04d}"
            self._next_id += 1

        self._active_tracks[key] = track
        self._track_to_global_id[key] = global_id

        # Record sighting in journey
        sighting = PersonSighting(
            global_person_id=global_id,
            camera_id=track.camera_id,
            track_id=track.track_id,
            first_seen=track.first_seen,
            last_seen=track.last_seen,
            similarity=round(best_similarity, 4) if best_similarity > 0 else 1.0,
        )

        if global_id not in self._journeys:
            self._journeys[global_id] = []
        self._journeys[global_id].append(sighting)

        return global_id

    def get_journey(self, global_person_id: str) -> list[PersonSighting]:
        """Retrieve chronological camera transitions for a given person."""
        return sorted(self._journeys.get(global_person_id, []), key=lambda s: s.first_seen)
