"""Camera floor-plane homography calibration tool for Project 5 Vision Edge."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import yaml
from fieldkit_vision.homography import CameraHomography

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calibrate_camera")


def calibrate_camera_from_points(
    image_points: list[list[float]],
    floor_points: list[list[float]],
) -> tuple[CameraHomography, float]:
    """Compute homography matrix and mean reprojection error in meters."""
    homog = CameraHomography(image_points=image_points, floor_points_meters=floor_points)

    # Compute reprojection error
    errors = []
    for img_pt, flr_pt in zip(image_points, floor_points, strict=False):
        proj_flr = homog.image_to_floor(img_pt)
        err = np.linalg.norm(np.array(proj_flr) - np.array(flr_pt))
        errors.append(err)

    mean_err = float(np.mean(errors))
    return homog, mean_err


def verify_camera_config(yaml_path: Path) -> dict[str, float | str | bool]:
    """Load camera YAML and verify homography condition number and reprojection error."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cam_id = data.get("camera_id", yaml_path.stem)
    homog_data = data.get("homography")
    if not homog_data:
        raise ValueError(f"No homography calibration found in {yaml_path}")

    img_pts = homog_data["image_points"]
    flr_pts = homog_data["floor_points_meters"]

    homog, mean_err = calibrate_camera_from_points(img_pts, flr_pts)
    cond_num = float(np.linalg.cond(homog.matrix))

    # Check non-degeneracy
    det = float(np.linalg.det(homog.matrix))
    is_valid = abs(det) > 1e-6 and mean_err < 0.05

    return {
        "camera_id": cam_id,
        "yaml_file": str(yaml_path),
        "condition_number": round(cond_num, 2),
        "mean_reprojection_error_m": round(mean_err, 6),
        "determinant": round(det, 4),
        "is_valid": is_valid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate camera floor-plane homography")
    parser.add_argument("--camera-id", type=str, default=None, help="Target camera ID")
    parser.add_argument("--config-dir", type=str, default="configs/cameras", help="Directory with camera YAML files")
    parser.add_argument("--verify-all", action="store_true", help="Verify all camera calibrations in config dir")
    args = parser.parse_args()

    cfg_dir = Path(args.config_dir)
    if not cfg_dir.exists():
        logger.error("Configuration directory %s not found.", cfg_dir)
        return

    yaml_files = list(cfg_dir.glob("*.yaml"))
    if args.camera_id:
        yaml_files = [p for p in yaml_files if p.stem == args.camera_id]

    print("\n" + "=" * 70)
    print("CAMERA FLOOR HOMOGRAPHY CALIBRATION VERIFICATION")
    print("=" * 70)

    for yf in sorted(yaml_files):
        try:
            res = verify_camera_config(yf)
            status = "VALID" if res["is_valid"] else "INVALID"
            print(f"Camera: {res['camera_id']:<18} Status: {status:<8} Error: {res['mean_reprojection_error_m']:.4f}m  Cond: {res['condition_number']}")
        except Exception as e:
            print(f"Camera: {yf.stem:<18} Error loading homography: {e}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
