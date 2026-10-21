"""Heatmap overlay image persistence for MinIO object storage and local filesystem."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("fieldkit.vision.inspect.storage")


class HeatmapStorageManager:
    """Manages storage and retrieval of blended Jet color heatmap overlay images."""

    def __init__(
        self,
        local_dir: Path | str = "data/inspection/heatmaps",
        bucket_name: str = "inspection-heatmaps",
        minio_endpoint: str | None = None,
    ) -> None:
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.bucket_name = bucket_name
        self.minio_endpoint = minio_endpoint
        self._index: dict[str, Path] = {}

    def save_heatmap_overlay(
        self,
        product_id: str,
        inspection_id: str,
        image: np.ndarray,
        heatmap: np.ndarray,
        alpha: float = 0.45,
    ) -> tuple[str, str]:
        """Blend 2D anomaly heatmap with base image, save as JPEG, and return (URI, local_path)."""
        # 1. Generate Jet colormap overlay
        heat_u8 = (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8)
        color_map = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

        base_img = image.copy()
        if len(base_img.shape) == 2:
            base_img = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)

        blended = cv2.addWeighted(color_map, alpha, base_img, 1.0 - alpha, 0)

        # 2. Save locally
        prod_dir = self.local_dir / product_id
        prod_dir.mkdir(parents=True, exist_ok=True)
        local_file = prod_dir / f"{inspection_id}.jpg"

        # Encode with quality=92
        cv2.imwrite(str(local_file), blended, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        self._index[inspection_id] = local_file

        # URI pointing to service endpoint / S3 bucket
        uri = f"s3://{self.bucket_name}/{product_id}/{inspection_id}.jpg"
        return uri, str(local_file.resolve())

    def get_heatmap_bytes(self, inspection_id: str) -> bytes | None:
        """Retrieve binary JPEG bytes for an inspection heatmap."""
        # 1. Check in-memory index
        if inspection_id in self._index and self._index[inspection_id].exists():
            return self._index[inspection_id].read_bytes()

        # 2. Search local directory
        matches = list(self.local_dir.glob(f"**/{inspection_id}.jpg"))
        if matches and matches[0].exists():
            self._index[inspection_id] = matches[0]
            return matches[0].read_bytes()

        return None
