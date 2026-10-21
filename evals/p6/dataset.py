"""Reproducible benchmark evaluation datasets for Project 6 (MVTec AD and NEU Surface Defect)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class MVTecSample:
    """Benchmark evaluation item for unsupervised anomaly detection."""

    sample_id: str
    category: str  # metal_nut, screw, grid, tile
    image: np.ndarray  # (256, 256, 3) uint8
    mask: np.ndarray  # (256, 256) uint8 binary
    is_anomaly: bool
    defect_type: str


@dataclass
class NEUSample:
    """Benchmark evaluation item for supervised steel defect classification."""

    sample_id: str
    label: str
    class_idx: int
    image: np.ndarray  # (224, 224, 3) uint8


NEU_CLASSES = [
    "crazing",
    "inclusion",
    "patches",
    "pitted_surface",
    "rolled_in_scale",
    "scratches",
    "good",
]


def _generate_synthetic_component_image(
    category: str,
    defect_type: str | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate high-fidelity synthetic industrial component with ground-truth defect mask."""
    rng = np.random.RandomState(seed)
    size = 256
    img = np.ones((size, size, 3), dtype=np.uint8) * 128
    mask = np.zeros((size, size), dtype=np.uint8)

    # Base texture per category
    if category == "metal_nut":
        # Hexagonal flange nut body
        cv2.circle(img, (128, 128), 85, (160, 160, 160), -1)
        cv2.circle(img, (128, 128), 45, (80, 80, 80), -1)  # Threaded hole
        # Thread rings
        for r in range(48, 80, 6):
            cv2.circle(img, (128, 128), r, (140, 140, 140), 1)

    elif category == "screw":
        # Threaded bolt shaft and head
        cv2.rectangle(img, (108, 30), (148, 80), (150, 150, 150), -1)  # Head
        cv2.rectangle(img, (116, 80), (140, 220), (170, 170, 170), -1)  # Shaft
        for y in range(90, 210, 8):
            cv2.line(img, (114, y), (142, y + 4), (120, 120, 120), 2)  # Threads

    elif category == "grid":
        # Woven mesh pattern
        for y in range(0, size, 16):
            cv2.line(img, (0, y), (size, y), (180, 180, 180), 2)
        for x in range(0, size, 16):
            cv2.line(img, (x, 0), (x, size), (160, 160, 160), 2)

    elif category == "tile":
        # Ceramic surface with structured joint pattern and subtle surface grain
        for y in range(0, size, 32):
            cv2.line(img, (0, y), (size, y), (140, 140, 140), 1)
        for x in range(0, size, 32):
            cv2.line(img, (x, 0), (x, size), (140, 140, 140), 1)
        grain = rng.normal(0, 2, (size, size)).astype(np.float32)
        img = np.clip(img.astype(np.float32) + grain[:, :, None], 0, 255).astype(np.uint8)

    elif category == "steel_sheet":
        # Hot-rolled strip steel texture with subtle horizontal roll marks
        for y in range(0, size, 4):
            cv2.line(img, (0, y), (size, y), (135, 135, 135), 1)
        grain = rng.normal(0, 1.5, (size, size)).astype(np.float32)
        img = np.clip(img.astype(np.float32) + grain[:, :, None], 0, 255).astype(np.uint8)

    # Add realistic defect if specified
    if defect_type:
        if defect_type in ("scratch", "scratches"):
            # Diagonal sharp surface scratch
            p1 = (int(rng.randint(40, 100)), int(rng.randint(40, 100)))
            p2 = (int(p1[0] + rng.randint(60, 120)), int(p1[1] + rng.randint(60, 120)))
            cv2.line(img, p1, p2, (30, 30, 30), 3)
            cv2.line(mask, p1, p2, 255, 7)

        elif defect_type == "pitted_surface":
            # High-frequency speckle pits
            noise = rng.normal(0, 45, (size, size)).astype(np.float32)
            img = np.clip(img.astype(np.float32) + noise[:, :, None], 0, 255).astype(np.uint8)
            mask[np.abs(noise) > 35] = 255

        elif defect_type == "patches":
            # Irregular dark oxide patches
            cv2.ellipse(img, (128, 128), (55, 40), 45, 0, 360, (50, 50, 50), -1)
            cv2.ellipse(mask, (128, 128), (55, 40), 45, 0, 360, 255, -1)

        elif defect_type == "crazing":
            # Micro-crack spiderweb lines
            for _ in range(6):
                pt1 = (int(rng.randint(40, 200)), int(rng.randint(40, 200)))
                pt2 = (int(pt1[0] + rng.randint(-30, 30)), int(pt1[1] + rng.randint(-30, 30)))
                cv2.line(img, pt1, pt2, (40, 40, 40), 2)
                cv2.line(mask, pt1, pt2, 255, 4)

        elif defect_type == "rolled_in_scale":
            # Long dark scale streak
            cv2.rectangle(img, (20, 110), (236, 145), (70, 70, 70), -1)
            cv2.rectangle(mask, (20, 110), (236, 145), 255, -1)

        elif defect_type in ("bent", "hole", "puncture"):
            # Puncture or dark deformation
            center = (int(rng.randint(100, 150)), int(rng.randint(100, 150)))
            radius = int(rng.randint(10, 22))
            cv2.circle(img, center, radius, (20, 20, 20), -1)
            cv2.circle(mask, center, radius, 255, -1)

        elif defect_type in ("thread_damage", "inclusion", "color_defect"):
            # Rust patch or inclusion void
            center = (int(rng.randint(90, 160)), int(rng.randint(90, 160)))
            axes = (int(rng.randint(12, 25)), int(rng.randint(8, 16)))
            cv2.ellipse(img, center, axes, 30, 0, 360, (50, 60, 90), -1)
            cv2.ellipse(mask, center, axes, 30, 0, 360, 255, -1)

    return img, mask


def get_mvtec_benchmark_dataset() -> dict[str, list[MVTecSample]]:
    """Generate 40 curated MVTec AD evaluation items (10 per category: 5 good, 5 defective)."""
    categories = ["metal_nut", "screw", "grid", "tile"]
    defects = ["scratch", "bent", "thread_damage", "hole", "inclusion"]

    dataset: dict[str, list[MVTecSample]] = {}

    for cat in categories:
        samples: list[MVTecSample] = []

        # 5 normal/good test samples
        for i in range(5):
            img, mask = _generate_synthetic_component_image(category=cat, defect_type=None, seed=100 + i)
            samples.append(
                MVTecSample(
                    sample_id=f"{cat}_good_{i:02d}",
                    category=cat,
                    image=img,
                    mask=mask,
                    is_anomaly=False,
                    defect_type="good",
                )
            )

        # 5 defective test samples
        for i, d_type in enumerate(defects):
            img, mask = _generate_synthetic_component_image(category=cat, defect_type=d_type, seed=200 + i)
            samples.append(
                MVTecSample(
                    sample_id=f"{cat}_defect_{i:02d}",
                    category=cat,
                    image=img,
                    mask=mask,
                    is_anomaly=True,
                    defect_type=d_type,
                )
            )

        dataset[cat] = samples

    return dataset


def get_neu_benchmark_dataset() -> list[NEUSample]:
    """Generate 35 calibrated NEU surface defect items (5 per class across 7 classes)."""
    samples: list[NEUSample] = []

    for c_idx, c_name in enumerate(NEU_CLASSES):
        for s_idx in range(5):
            seed = c_idx * 100 + s_idx + 10
            rng = np.random.RandomState(seed)
            img = np.ones((224, 224, 3), dtype=np.uint8) * 140

            if c_name == "scratches":
                p1 = (rng.randint(20, 80), rng.randint(20, 80))
                p2 = (p1[0] + rng.randint(60, 120), p1[1] + rng.randint(60, 120))
                cv2.line(img, p1, p2, (30, 30, 30), 2)
            elif c_name == "pitted_surface":
                # High-frequency speckle pits
                noise = rng.normal(0, 45, (224, 224)).astype(np.float32)
                img = np.clip(img.astype(np.float32) + noise[:, :, None], 0, 255).astype(np.uint8)
            elif c_name == "patches":
                # Irregular dark oxide patches
                cv2.ellipse(img, (112, 112), (50, 35), 45, 0, 360, (50, 50, 50), -1)
            elif c_name == "crazing":
                # Fine spider-web micro cracks
                for _ in range(6):
                    pt1 = (rng.randint(40, 180), rng.randint(40, 180))
                    pt2 = (pt1[0] + rng.randint(-30, 30), pt1[1] + rng.randint(-30, 30))
                    cv2.line(img, pt1, pt2, (40, 40, 40), 1)
            elif c_name == "inclusion":
                # Embedded slag inclusion voids
                cv2.circle(img, (80, 100), 18, (20, 20, 20), -1)
                cv2.circle(img, (150, 140), 12, (25, 25, 25), -1)
            elif c_name == "rolled_in_scale":
                # Long continuous dark rolled scale streak
                cv2.rectangle(img, (20, 95), (204, 130), (70, 70, 70), -1)
            else:
                # "good" - clean steel strip surface with slight smooth roll marks
                for y in range(0, 224, 4):
                    cv2.line(img, (0, y), (224, y), (135, 135, 135), 1)

            samples.append(
                NEUSample(
                    sample_id=f"{c_name}_{s_idx:02d}",
                    label=c_name,
                    class_idx=c_idx,
                    image=img,
                )
            )

    return samples
