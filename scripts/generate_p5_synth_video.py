"""Generate lightweight synthetic plant simulation MP4 videos for local RTSP camera streaming."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def generate_plant_clip(
    output_path: str | Path,
    camera_id: str,
    duration_sec: float = 6.0,
    fps: float = 25.0,
    width: int = 640,
    height: int = 360,
) -> Path:
    """Generate a synthetic plant video clip with timestamps and simulated moving objects."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    total_frames = int(duration_sec * fps)
    for frame_idx in range(total_frames):
        # Industrial dark floor background
        frame = np.full((height, width, 3), 45, dtype=np.uint8)

        # Floor grid lines
        for y in range(0, height, 40):
            cv2.line(frame, (0, y), (width, y), (60, 60, 60), 1)
        for x in range(0, width, 40):
            cv2.line(frame, (x, 0), (x, height), (60, 60, 60), 1)

        # Camera watermark overlay
        timestamp_str = f"2026-10-21 12:00:{frame_idx / fps:05.2f}"
        cv2.putText(
            frame,
            f"{camera_id.upper()} | {timestamp_str} | F:{frame_idx}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 200),
            2,
            cv2.LINE_AA,
        )

        # Simulated dynamic objects based on camera
        t = frame_idx / total_frames
        if "press" in camera_id:
            # Danger zone polygon indicator
            pts = np.array([[100, 150], [540, 150], [590, 320], [50, 320]], np.int32)
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 220), thickness=2)
            # Simulated worker moving across
            wx = int(120 + t * 380)
            wy = int(200 + np.sin(t * np.pi * 4) * 15)
            # Worker body
            cv2.rectangle(frame, (wx - 15, wy - 30), (wx + 15, wy + 40), (200, 120, 50), -1)
            # Hardhat (yellow)
            cv2.circle(frame, (wx, wy - 35), 8, (0, 220, 255), -1)

        elif "logistics" in camera_id:
            # Forklift lane
            cv2.line(frame, (80, 100), (80, 350), (0, 200, 255), 2)
            cv2.line(frame, (560, 100), (560, 350), (0, 200, 255), 2)
            # Forklift moving
            fx = int(200 + t * 240)
            cv2.rectangle(frame, (fx - 35, 180), (fx + 35, 260), (0, 140, 255), -1)
            cv2.putText(
                frame, "FORKLIFT-01", (fx - 30, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1
            )
            # Pedestrian
            px = int(450 - t * 80)
            cv2.rectangle(frame, (px - 10, 210), (px + 10, 270), (180, 180, 80), -1)

        else:
            # General motion
            x = int(50 + t * 500)
            cv2.rectangle(frame, (x - 20, 160), (x + 20, 220), (100, 200, 100), -1)

        writer.write(frame)

    writer.release()
    return output_path


def generate_all_test_videos(data_dir: str | Path = "data/p5/videos") -> list[Path]:
    """Generate all 4 standard camera simulation video clips."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cams = ["cam1_press", "cam2_logistics", "cam3_assembly", "cam4_perimeter"]
    paths = []
    for cam in cams:
        p = data_dir / f"{cam}.mp4"
        if not p.exists() or p.stat().st_size == 0:
            generate_plant_clip(p, cam)
        paths.append(p)
    return paths


if __name__ == "__main__":
    generated = generate_all_test_videos()
    print(f"Generated {len(generated)} test videos in data/p5/videos/")
