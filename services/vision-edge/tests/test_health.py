"""Unit tests for camera health diagnostics (frozen, black, blur, and view shift detection)."""

from __future__ import annotations

import cv2
import numpy as np
from fieldkit_vision.health import CameraHealthConfig, CameraHealthMonitor, HealthStatus


def _create_synthetic_test_frame(pattern_seed: int = 42) -> np.ndarray:
    """Generate a realistic test image with rich textures, edges, and corners for ORB detection."""
    np.random.seed(pattern_seed)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add geometric shapes and high-frequency textures
    cv2.rectangle(img, (50, 50), (250, 350), (120, 200, 80), -1)
    cv2.circle(img, (450, 240), 120, (50, 100, 220), -1)
    cv2.putText(
        img,
        "HALDEN DE-HAM PRESS 01",
        (100, 420),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )
    # Add scattered noise/dots to create strong corner keypoints
    for _ in range(100):
        x = np.random.randint(0, 640)
        y = np.random.randint(0, 480)
        cv2.circle(img, (x, y), 3, (255, 255, 0), -1)
    return img


def test_health_normal_feed() -> None:
    """Verify normal moving, properly illuminated feed produces HEALTHY status."""
    monitor = CameraHealthMonitor(camera_id="cam1_press")
    ref_frame = _create_synthetic_test_frame(pattern_seed=1)
    monitor.set_reference_frame(ref_frame)

    # Feed normal frames with slight motion/variation
    frame1 = _create_synthetic_test_frame(pattern_seed=2)
    report = monitor.evaluate_frame(frame1, timestamp=10.0, processed_fps=5.0)

    assert report.camera_id == "cam1_press"
    assert report.status == HealthStatus.HEALTHY
    assert report.is_frozen is False
    assert report.is_black is False
    assert report.is_blurred is False
    assert report.is_view_shifted is False
    assert report.processed_fps == 5.0
    assert report.laplacian_variance > 50.0


def test_health_frozen_frame() -> None:
    """Verify identical frames for duration trigger frozen detection."""
    monitor = CameraHealthMonitor(
        camera_id="cam1_press",
        config=CameraHealthConfig(frozen_duration_sec=2.0),
    )
    frame = _create_synthetic_test_frame(pattern_seed=5)
    monitor.set_reference_frame(frame)

    # Frame 1 at t=0
    r1 = monitor.evaluate_frame(frame, timestamp=0.0, processed_fps=5.0)
    assert r1.is_frozen is False

    # Same frame at t=1.0 (not yet 2.0s duration)
    r2 = monitor.evaluate_frame(frame, timestamp=1.0, processed_fps=5.0)
    assert r2.is_frozen is False

    # Same frame at t=2.5 (exceeds frozen_duration_sec)
    r3 = monitor.evaluate_frame(frame, timestamp=2.5, processed_fps=5.0)
    assert r3.is_frozen is True
    assert r3.status == HealthStatus.CRITICAL


def test_health_black_frame() -> None:
    """Verify low intensity frame (e.g. covered lens) triggers black frame detection."""
    monitor = CameraHealthMonitor(camera_id="cam2_logistics")
    # Pure dark frame with mean intensity < 10
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8) + 5

    report = monitor.evaluate_frame(black_frame, timestamp=10.0, processed_fps=5.0)
    assert report.is_black is True
    assert report.status == HealthStatus.CRITICAL
    assert report.mean_intensity < 15.0


def test_health_blur_detection() -> None:
    """Verify heavily blurred / defocused frame triggers blur detection."""
    monitor = CameraHealthMonitor(
        camera_id="cam3_assembly",
        config=CameraHealthConfig(blur_threshold=60.0),
    )
    sharp_frame = _create_synthetic_test_frame(pattern_seed=10)
    # Apply severe Gaussian blur
    blurred_frame = cv2.GaussianBlur(sharp_frame, (51, 51), 20.0)

    report = monitor.evaluate_frame(blurred_frame, timestamp=10.0, processed_fps=5.0)
    assert report.is_blurred is True
    assert report.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL)
    assert report.laplacian_variance < 60.0


def test_health_view_shift_detection() -> None:
    """Verify significant camera viewpoint shift (ORB match drop) triggers view shift alert."""
    monitor = CameraHealthMonitor(
        camera_id="cam4_perimeter",
        config=CameraHealthConfig(view_shift_ratio_min=0.30),
    )
    ref_frame = _create_synthetic_test_frame(pattern_seed=20)
    monitor.set_reference_frame(ref_frame)

    # Shifted frame: completely different scene (camera pointed elsewhere)
    shifted_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(shifted_frame, (300, 300), (600, 450), (200, 50, 50), -1)
    for _ in range(50):
        cv2.circle(
            shifted_frame,
            (np.random.randint(0, 640), np.random.randint(0, 480)),
            2,
            (0, 255, 255),
            -1,
        )

    report = monitor.evaluate_frame(shifted_frame, timestamp=10.0, processed_fps=5.0)
    assert report.is_view_shifted is True
    assert report.status == HealthStatus.CRITICAL
    assert report.orb_match_ratio < 0.30
