"""Unit tests for 4-point floor-plane metric homography calibration."""

from __future__ import annotations

import numpy as np
import pytest
from fieldkit_vision.homography import (
    CameraHomography,
    compute_metric_distance,
    compute_metric_speed,
)
from fieldkit_vision.models import HomographyConfig


@pytest.fixture
def sample_homography() -> CameraHomography:
    """Fixture with a known perspective trapezoid to rectangular floor bay (6m x 8m)."""
    # Image points: trapezoid perspective view
    image_points = [
        [350.0, 420.0],  # Top-left
        [950.0, 420.0],  # Top-right
        [1120.0, 920.0],  # Bottom-right
        [220.0, 920.0],  # Bottom-left
    ]
    # Real-world metric floor points in meters
    floor_points = [
        [0.0, 0.0],  # (X=0m, Y=0m)
        [6.0, 0.0],  # (X=6m, Y=0m) width=6m
        [6.0, 8.0],  # (X=6m, Y=8m) length=8m
        [0.0, 8.0],  # (X=0m, Y=8m)
    ]
    return CameraHomography(image_points=image_points, floor_points_meters=floor_points)


def test_homography_initialization(sample_homography: CameraHomography) -> None:
    """Verify homography matrix is non-degenerate and invertible."""
    assert sample_homography.matrix.shape == (3, 3)
    assert sample_homography.inverse_matrix.shape == (3, 3)
    # Check identity on product H * H^-1
    ident = sample_homography.matrix @ sample_homography.inverse_matrix
    ident /= ident[2, 2]
    np.testing.assert_allclose(ident, np.eye(3), atol=1e-4)


def test_homography_exact_corner_projections(sample_homography: CameraHomography) -> None:
    """Verify that the 4 calibrated image corners project to the exact floor coordinates."""
    # Top-left
    p1 = sample_homography.image_to_floor((350.0, 420.0))
    np.testing.assert_allclose(p1, (0.0, 0.0), atol=1e-3)

    # Top-right
    p2 = sample_homography.image_to_floor((950.0, 420.0))
    np.testing.assert_allclose(p2, (6.0, 0.0), atol=1e-3)

    # Bottom-right
    p3 = sample_homography.image_to_floor((1120.0, 920.0))
    np.testing.assert_allclose(p3, (6.0, 8.0), atol=1e-3)

    # Bottom-left
    p4 = sample_homography.image_to_floor((220.0, 920.0))
    np.testing.assert_allclose(p4, (0.0, 8.0), atol=1e-3)


def test_homography_inversion_roundtrip(sample_homography: CameraHomography) -> None:
    """Verify that image -> floor -> image roundtrip is lossless."""
    orig_pixel = (640.0, 670.0)  # Near center of ground trapezoid
    floor_coord = sample_homography.image_to_floor(orig_pixel)
    roundtrip_pixel = sample_homography.floor_to_image(floor_coord)

    np.testing.assert_allclose(orig_pixel, roundtrip_pixel, atol=1e-3)


def test_homography_batch_transformation(sample_homography: CameraHomography) -> None:
    """Verify vectorized batch projection for multi-object tracking."""
    pixels = np.array([
        [350.0, 420.0],
        [950.0, 420.0],
        [1120.0, 920.0],
        [220.0, 920.0],
    ])
    floor_coords = sample_homography.image_to_floor_batch(pixels)
    assert floor_coords.shape == (4, 2)
    np.testing.assert_allclose(floor_coords[0], [0.0, 0.0], atol=1e-3)
    np.testing.assert_allclose(floor_coords[1], [6.0, 0.0], atol=1e-3)
    np.testing.assert_allclose(floor_coords[2], [6.0, 8.0], atol=1e-3)
    np.testing.assert_allclose(floor_coords[3], [0.0, 8.0], atol=1e-3)


def test_compute_metric_distance() -> None:
    """Verify Euclidean metric distance between ground-plane coordinates in meters."""
    # Pedestrian at (2.0m, 4.0m), Forklift at (3.5m, 6.0m)
    # dx = 1.5, dy = 2.0 -> dist = sqrt(1.5^2 + 2.0^2) = sqrt(2.25 + 4.0) = sqrt(6.25) = 2.5m
    d = compute_metric_distance((2.0, 4.0), (3.5, 6.0))
    assert round(d, 4) == 2.5000

    # Test proximity threshold check (< 2.0m)
    d_close = compute_metric_distance((2.0, 4.0), (3.0, 4.5))
    # dx = 1.0, dy = 0.5 -> dist = sqrt(1 + 0.25) = 1.118m < 2.0m
    assert d_close < 2.0


def test_compute_metric_speed() -> None:
    """Verify speed calculation in meters/second from trajectory timestamps."""
    # Moved 3 meters in 1.5 seconds -> 2.0 m/s
    speed = compute_metric_speed(
        pos1=(1.0, 2.0),
        time1=100.0,
        pos2=(4.0, 2.0),
        time2=101.5,
    )
    assert round(speed, 2) == 2.00


def test_homography_config_roundtrip(sample_homography: CameraHomography) -> None:
    """Verify serialization to and from HomographyConfig model."""
    config = sample_homography.to_config()
    assert isinstance(config, HomographyConfig)
    assert len(config.image_points) == 4
    assert len(config.floor_points_meters) == 4

    reconstructed = CameraHomography.from_config(config)
    np.testing.assert_allclose(sample_homography.matrix, reconstructed.matrix, atol=1e-5)


def test_invalid_homography_points() -> None:
    """Verify validation error when fewer than 4 points are supplied."""
    with pytest.raises(ValueError, match="at least 4 non-collinear point pairs"):
        CameraHomography(
            image_points=[[0.0, 0.0], [1.0, 1.0]],
            floor_points_meters=[[0.0, 0.0], [1.0, 1.0]],
        )
