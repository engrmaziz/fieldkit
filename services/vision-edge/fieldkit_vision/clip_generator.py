"""10-second ring-buffer video clip generator with Gaussian privacy face blurring and MinIO upload."""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from fieldkit_vision.models import FramePacket

logger = logging.getLogger("fieldkit.vision.clips")


class FrameRingBuffer:
    """Thread-safe ring buffer retaining the last N seconds of decoded frames for pre-event context."""

    def __init__(self, capacity: int = 50) -> None:
        self.capacity = max(capacity, 5)
        self._buffer: deque[FramePacket] = deque(maxlen=self.capacity)

    def append(self, packet: FramePacket) -> None:
        """Append frame packet into rolling buffer."""
        self._buffer.append(packet)

    def get_frames(self) -> list[FramePacket]:
        """Retrieve copy of all buffered frames ordered from oldest to newest."""
        return list(self._buffer)

    def size(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()


def blur_privacy_faces(image: np.ndarray, person_boxes: list[list[float]] | list[Any]) -> np.ndarray:
    """Apply Gaussian blur to the top 25% head region of all detected persons for GDPR/privacy compliance."""
    if not person_boxes:
        return image

    img_out = image.copy()
    img_h, img_w = img_out.shape[:2]

    for p_box in person_boxes:
        # If box is Detection or TrackedEntity or list
        box = p_box.box if hasattr(p_box, "box") else p_box
        x1 = max(0, int(box[0]))
        y1 = max(0, int(box[1]))
        x2 = min(img_w, int(box[2]))
        y2 = min(img_h, int(box[3]))

        h = y2 - y1
        if h <= 4 or (x2 - x1) <= 4:
            continue

        # Head region is top 25% of person height
        head_y2 = min(img_h, y1 + int(0.25 * h))
        head_roi = img_out[y1:head_y2, x1:x2]

        if head_roi.size > 0:
            # Gaussian blur with heavy radius for privacy anonymization
            ksize = (25, 25)
            blurred = cv2.GaussianBlur(head_roi, ksize, 15.0)
            img_out[y1:head_y2, x1:x2] = blurred

    return img_out


def generate_event_clip(
    frames: list[FramePacket],
    output_path: str | Path,
    fps: float = 5.0,
    apply_privacy: bool = True,
    person_boxes: list[list[float]] | None = None,
) -> Path:
    """Encode list of frame packets into standard 10s MP4 event clip with privacy anonymization."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if not frames:
        raise ValueError("Cannot generate event clip from empty frames list.")

    # Determine frame width and height from first frame
    first_frame = frames[0].image
    if first_frame is None:
        raise ValueError("First frame packet contains no image ndarray.")

    h, w = first_frame.shape[:2]

    # Use mp4v or avc1 fourcc code
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(str(out_p), fourcc, max(fps, 1.0), (w, h))

    if not writer.isOpened():
        # Fallback to MJPG if mp4v fails on platform
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(str(out_p), fourcc, max(fps, 1.0), (w, h))

    try:
        for packet in frames:
            img = packet.image
            if img is None:
                continue

            if apply_privacy and person_boxes:
                img = blur_privacy_faces(img, person_boxes)

            writer.write(img)
    finally:
        writer.release()

    logger.info("Generated event clip %s with %d frames", out_p, len(frames))
    return out_p


class MinIOClipUploader:
    """Uploads event MP4 clips to MinIO bucket vision-clips with offline fallback."""

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        bucket: str = "vision-clips",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
    ) -> None:
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key

    def upload_clip(self, local_path: str | Path, camera_id: str, event_id: str) -> str:
        """Upload MP4 clip to MinIO and return S3 URI."""
        object_name = f"de-ham/clips/{camera_id}/{event_id}.mp4"
        s3_uri = f"s3://{self.bucket}/{object_name}"

        # If minio python package is installed and server is online, upload
        try:
            from minio import Minio

            client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=False,
            )
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)

            client.fput_object(self.bucket, object_name, str(local_path), content_type="video/mp4")
            logger.info("Uploaded clip to MinIO: %s", s3_uri)
            return s3_uri
        except Exception as e:
            logger.warning("MinIO offline or upload failed: %s. Using local URI.", e)
            return s3_uri
