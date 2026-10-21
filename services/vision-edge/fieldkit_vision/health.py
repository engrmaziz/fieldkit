"""Camera Health Diagnostics and Quality Degradation Monitoring Engine.

Detects frozen video streams (mean absolute frame difference < 1.0 for sustained window),
black/occluded frames (mean intensity < 15.0), severe lens blur/defocus (Laplacian variance),
and camera view shifts (ORB keypoint descriptors dropping below 30% of reference baseline).
"""

from __future__ import annotations

from enum import StrEnum

import cv2
import numpy as np
from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Overall camera health assessment."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class CameraHealthConfig(BaseModel):
    """Configurable thresholds for camera quality checks."""

    frozen_duration_sec: float = Field(default=10.0, ge=1.0)
    frozen_diff_threshold: float = Field(default=1.0, ge=0.0)
    black_intensity_threshold: float = Field(default=15.0, ge=0.0)
    blur_threshold: float = Field(default=50.0, ge=0.0)
    blur_relative_drop: float = Field(default=0.25, ge=0.0, le=1.0)
    view_shift_ratio_min: float = Field(default=0.30, ge=0.0, le=1.0)
    target_fps: float = Field(default=5.0, ge=1.0)
    fps_degraded_threshold: float = Field(default=2.5, ge=0.5)


class CameraHealthReport(BaseModel):
    """Detailed health diagnosis for an evaluated frame/timestamp."""

    camera_id: str
    timestamp: float
    status: HealthStatus
    is_frozen: bool = False
    is_black: bool = False
    is_blurred: bool = False
    is_view_shifted: bool = False
    processed_fps: float = 0.0
    laplacian_variance: float = 0.0
    mean_intensity: float = 0.0
    mean_abs_diff: float = 0.0
    orb_match_ratio: float = 1.0
    reconnect_count: int = 0
    diagnostics: list[str] = Field(default_factory=list)


class CameraHealthMonitor:
    """Monitors live camera feeds and diagnoses hardware/stream abnormalities."""

    def __init__(
        self,
        camera_id: str,
        config: CameraHealthConfig | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.config = config or CameraHealthConfig()
        self._last_frame: np.ndarray | None = None
        self._last_timestamp: float | None = None
        self._frozen_start_time: float | None = None

        self._reference_frame: np.ndarray | None = None
        self._reference_descriptors: np.ndarray | None = None
        self._reference_keypoint_count: int = 0
        self._reference_blur_baseline: float = 100.0

        # Feature matching for view shift detection
        self._orb = cv2.ORB_create(nfeatures=500)  # type: ignore[attr-defined]
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def set_reference_frame(self, frame: np.ndarray) -> None:
        """Register the baseline reference frame for view shift and blur comparisons."""
        if frame is None or frame.size == 0:
            return

        self._reference_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._reference_blur_baseline = max(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1.0)

        # Detect baseline ORB keypoints and descriptors
        kps, descs = self._orb.detectAndCompute(gray, None)
        self._reference_descriptors = descs
        self._reference_keypoint_count = len(kps) if kps is not None else 0

    def evaluate_frame(
        self,
        frame: np.ndarray,
        timestamp: float,
        processed_fps: float,
        reconnect_count: int = 0,
    ) -> CameraHealthReport:
        """Run complete diagnostic battery on the latest frame."""
        if frame is None or frame.size == 0:
            return CameraHealthReport(
                camera_id=self.camera_id,
                timestamp=timestamp,
                status=HealthStatus.CRITICAL,
                processed_fps=processed_fps,
                reconnect_count=reconnect_count,
                diagnostics=["Empty or null frame received"],
            )

        diagnostics: list[str] = []
        is_black = False
        is_blurred = False
        is_frozen = False
        is_view_shifted = False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_intensity = float(frame.mean())
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 1. Black / Occluded Check
        if mean_intensity < self.config.black_intensity_threshold:
            is_black = True
            diagnostics.append(
                f"Black/occluded frame: mean intensity {mean_intensity:.1f} < {self.config.black_intensity_threshold}"
            )

        # 2. Blur / Defocus Check
        rel_baseline = self._reference_blur_baseline * self.config.blur_relative_drop
        if lap_var < self.config.blur_threshold or lap_var < rel_baseline:
            is_blurred = True
            diagnostics.append(
                f"Blurred image: Laplacian variance {lap_var:.1f} < threshold {self.config.blur_threshold}"
            )

        # 3. Frozen Frame Check
        mean_abs_diff = 100.0
        if self._last_frame is not None and self._last_frame.shape == frame.shape:
            # Mean absolute pixel difference
            diff_arr = cv2.absdiff(frame, self._last_frame)
            mean_abs_diff = float(diff_arr.mean())

            if mean_abs_diff < self.config.frozen_diff_threshold:
                if self._frozen_start_time is None:
                    self._frozen_start_time = (
                        self._last_timestamp if self._last_timestamp is not None else timestamp
                    )

                elapsed_frozen = timestamp - self._frozen_start_time
                if elapsed_frozen >= self.config.frozen_duration_sec:
                    is_frozen = True
                    diagnostics.append(
                        f"Frozen stream: static image for {elapsed_frozen:.1f}s (diff {mean_abs_diff:.2f})"
                    )
            else:
                self._frozen_start_time = None
        else:
            self._frozen_start_time = None

        self._last_frame = frame.copy()
        self._last_timestamp = timestamp

        # 4. View Shift Check (ORB Keypoints vs Reference Frame)
        orb_match_ratio = 1.0
        if self._reference_descriptors is not None and self._reference_keypoint_count > 0:
            kps, descs = self._orb.detectAndCompute(gray, None)
            if descs is not None and len(descs) > 0:
                try:
                    matches = self._matcher.match(self._reference_descriptors, descs)
                    # Filter good inlier matches by Hamming distance
                    good_matches = [m for m in matches if m.distance < 50.0]
                    orb_match_ratio = len(good_matches) / max(1, self._reference_keypoint_count)
                except Exception:
                    orb_match_ratio = 0.0
            else:
                orb_match_ratio = 0.0

            if orb_match_ratio < self.config.view_shift_ratio_min:
                is_view_shifted = True
                diagnostics.append(
                    f"Camera view shift: ORB inliers {orb_match_ratio:.2%} < threshold {self.config.view_shift_ratio_min:.2%}"
                )

        # 5. Low FPS Check
        if processed_fps < self.config.fps_degraded_threshold:
            diagnostics.append(
                f"Degraded ingest FPS: {processed_fps:.1f} < {self.config.fps_degraded_threshold:.1f}"
            )

        # Determine aggregate status
        if is_black or is_frozen or is_view_shifted:
            status = HealthStatus.CRITICAL
        elif is_blurred or processed_fps < self.config.fps_degraded_threshold:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return CameraHealthReport(
            camera_id=self.camera_id,
            timestamp=timestamp,
            status=status,
            is_frozen=is_frozen,
            is_black=is_black,
            is_blurred=is_blurred,
            is_view_shifted=is_view_shifted,
            processed_fps=processed_fps,
            laplacian_variance=round(lap_var, 2),
            mean_intensity=round(mean_intensity, 2),
            mean_abs_diff=round(mean_abs_diff, 2),
            orb_match_ratio=round(orb_match_ratio, 4),
            reconnect_count=reconnect_count,
            diagnostics=diagnostics,
        )
