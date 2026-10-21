"""Dataset manifest management, content hashing, and perceptual deduplication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class SplitType(StrEnum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"
    RECENT_EVAL = "recent_eval"


def compute_sha256(data: bytes) -> str:
    """Compute cryptographic SHA-256 content digest."""
    return hashlib.sha256(data).hexdigest()


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> int:
    """Compute 64-bit difference hash (dHash) for perceptual image comparison."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Resize to (hash_size + 1, hash_size)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)

    # Compute horizontal gradients
    diff = resized[:, 1:] > resized[:, :-1]

    # Convert binary matrix to 64-bit integer
    h = 0
    for val in diff.flatten():
        h = (h << 1) | int(val)
    return h


def hamming_distance(h1: int, h2: int) -> int:
    """Calculate Hamming bit distance between two 64-bit perceptual hashes."""
    return bin(h1 ^ h2).count("1")


@dataclass
class ManifestItem:
    """Single annotated image record in dataset manifest."""

    item_id: str
    relative_path: str
    sha256: str
    dhash: int
    label: str
    is_anomaly: bool
    split: SplitType = SplitType.TRAIN
    product_id: str = "generic"
    mask_path: str | None = None
    defect_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetManifest:
    """Versioned dataset manifest tracking content hashes and splits."""

    dataset_name: str
    version: str
    items: list[ManifestItem] = field(default_factory=list)
    created_at: str = ""

    def add_item(self, item: ManifestItem) -> None:
        self.items.append(item)

    def get_split(self, split: SplitType) -> list[ManifestItem]:
        return [it for it in self.items if it.split == split]

    def deduplicate_cross_splits(self, max_hamming_distance: int = 2) -> tuple[DatasetManifest, int]:
        """Detect and drop near-identical images across train and test splits to prevent data leakage."""
        train_items = [it for it in self.items if it.split == SplitType.TRAIN]
        eval_items = [it for it in self.items if it.split in (SplitType.VAL, SplitType.TEST)]

        dropped_count = 0
        cleaned_eval_items: list[ManifestItem] = []

        for e_item in eval_items:
            is_leak = False
            for t_item in train_items:
                if hamming_distance(e_item.dhash, t_item.dhash) <= max_hamming_distance:
                    is_leak = True
                    dropped_count += 1
                    break
            if not is_leak:
                cleaned_eval_items.append(e_item)

        other_items = [it for it in self.items if it.split not in (SplitType.TRAIN, SplitType.VAL, SplitType.TEST)]
        cleaned_manifest = DatasetManifest(
            dataset_name=self.dataset_name,
            version=f"{self.version}-deduped",
            items=train_items + cleaned_eval_items + other_items,
            created_at=self.created_at,
        )
        return cleaned_manifest, dropped_count

    def to_json(self) -> str:
        """Serialize manifest to JSON string."""
        raw_items = []
        for it in self.items:
            d = asdict(it)
            d["split"] = it.split.value
            raw_items.append(d)

        data = {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "created_at": self.created_at,
            "total_items": len(self.items),
            "items": raw_items,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, text: str) -> DatasetManifest:
        """Parse manifest from JSON string."""
        data = json.loads(text)
        items = []
        for d in data.get("items", []):
            d["split"] = SplitType(d["split"])
            items.append(ManifestItem(**d))

        return cls(
            dataset_name=data["dataset_name"],
            version=data["version"],
            items=items,
            created_at=data.get("created_at", ""),
        )

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> DatasetManifest:
        p = Path(path)
        return cls.from_json(p.read_text(encoding="utf-8"))
