"""Floor-plane metric homography calibration, perspective projection, and distance calculation."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from fieldkit_vision.models import HomographyConfig

logger = logging.getLogger("fieldkit.vision.homography")


def compute_metric_distance(pos1: tuple[float, float], pos2: tuple[float, float]) -> float:
    """Compute physical Euclidean distance in meters between two ground coordinates."""
    dx = pos1[0] - pos2[0]
    dy = pos1[1] - pos2[1]
    return float(np.sqrt(dx * dx + dy * dy))


def compute_metric_speed(
    pos1: tuple[float, float],
    time1: float,
    pos2: tuple[float, float],
    time2: float,
) -> float:
    """Compute scalar speed in meters per second between two timestamped positions."""
    dt = abs(time2 - time1)
    if dt < 1e-4:
        return 0.0
    dist = compute_metric_distance(pos1, pos2)
    return dist / dt


class CameraHomography:
    """Planar metric homography projection mapping image pixels to physical floor meters."""

    def __init__(
        self,
        image_points: list[list[float]] | np.ndarray,
        floor_points_meters: list[list[float]] | np.ndarray,
    ) -> None:
        src = np.array(image_points, dtype=np.float32)
        dst = np.array(floor_points_meters, dtype=np.float32)

        if len(src) < 4 or len(dst) < 4 or len(src) != len(dst):
            raise ValueError(
                f"Homography calibration requires at least 4 non-collinear point pairs, got {len(src)} and {len(dst)}."
            )

        # Reshape for OpenCV perspective transform
        src_pts = src.reshape(-1, 1, 2)
        dst_pts = dst.reshape(-1, 1, 2)

        # Compute forward perspective transformation (Image -> Floor Meters)
        h_matrix, _ = cv2.findHomography(src_pts, dst_pts, method=0)
        if h_matrix is None:
            raise ValueError("Failed to compute valid homography matrix from provided point correspondences.")

        self.matrix: np.ndarray = h_matrix.astype(np.float64)
        try:
            self.inverse_matrix: np.ndarray = np.linalg.inv(self.matrix)
        except np.linalg.LinAlgError as e:
            raise ValueError(f"Homography matrix is singular or non-invertible: {e}") from e

        self._image_points = src.tolist()
        self._floor_points = dst.tolist()

    def image_to_floor(self, point: tuple[float, float] | list[float]) -> tuple[float, float]:
        """Project a single (u, v) image pixel point to (X, Y) metric floor coordinates in meters."""
        pt = np.array([[[point[0], point[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.matrix)
        out = transformed[0, 0]
        return float(out[0]), float(out[1])

    def image_to_floor_batch(self, points: np.ndarray) -> np.ndarray:
        """Batch project (N, 2) image pixel points to (N, 2) floor coordinates in meters."""
        if len(points) == 0:
            return np.empty((0, 2), dtype=np.float64)
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(pts, self.matrix)
        return transformed.reshape(-1, 2).astype(np.float64)

    def floor_to_image(self, point: tuple[float, float] | list[float]) -> tuple[float, float]:
        """Project physical (X, Y) floor coordinates in meters back to (u, v) image pixel coordinates."""
        pt = np.array([[[point[0], point[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.inverse_matrix)
        out = transformed[0, 0]
        return float(out[0]), float(out[1])

    def floor_to_image_batch(self, points: np.ndarray) -> np.ndarray:
        """Batch project physical (N, 2) floor coordinates back to (N, 2) image pixel coordinates."""
        if len(points) == 0:
            return np.empty((0, 2), dtype=np.float64)
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(pts, self.inverse_matrix)
        return transformed.reshape(-1, 2).astype(np.float64)

    def to_config(self) -> HomographyConfig:
        """Serialize homography points to Pydantic HomographyConfig."""
        return HomographyConfig(
            image_points=self._image_points,
            floor_points_meters=self._floor_points,
        )

    @classmethod
    def from_config(cls, config: HomographyConfig) -> CameraHomography:
        """Create CameraHomography from HomographyConfig."""
        return cls(
            image_points=config.image_points,
            floor_points_meters=config.floor_points_meters,
        )

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> CameraHomography | None:
        """Create CameraHomography from camera YAML dictionary."""
        homog_data = data.get("homography")
        if not homog_data or not homog_data.get("image_points") or not homog_data.get("floor_points_meters"):
            return None
        return cls(
            image_points=homog_data["image_points"],
            floor_points_meters=homog_data["floor_points_meters"],
        )
