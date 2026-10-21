"""Dataset preparation and deduplication pipeline for Project 5 PPE + Forklift YOLO model."""

from __future__ import annotations

import io
import logging
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_dataset")

# Unified Target Classes
TARGET_CLASSES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "forklift",
}

# Source 1: archive.zip (Construction Site Safety / Roboflow v28)
# Raw classes: [Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, machinery, vehicle]
ARCHIVE_1_MAP = {
    0: 1,  # Hardhat -> helmet
    2: 2,  # NO-Hardhat -> no_helmet
    5: 0,  # Person -> person
    7: 3,  # Safety Vest -> vest
    8: 4,  # machinery -> forklift
    9: 4,  # vehicle -> forklift
}

# Source 2: archive (1).zip (Personal-Protective-Equipment Dataset)
# Raw classes: ['helmet', 'no_helmet', 'no_vest', 'person', 'vest']
ARCHIVE_2_MAP = {
    0: 1,  # helmet -> helmet
    1: 2,  # no_helmet -> no_helmet
    3: 0,  # person -> person
    4: 3,  # vest -> vest
}


def compute_dhash(img: Image.Image, hash_size: int = 8) -> int:
    """Compute 64-bit difference perceptual hash for duplicate detection."""
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    pixels = np.array(resized)
    diff = pixels[:, 1:] > pixels[:, :-1]
    return int("".join(["1" if x else "0" for x in diff.flatten()]), 2)


def hamming_distance(h1: int, h2: int) -> int:
    """Compute bitwise Hamming distance between two 64-bit integer hashes."""
    return bin(h1 ^ h2).count("1")


class DatasetPreparer:
    """Extracts, standardizes classes, and deduplicates PPE images across splits."""

    def __init__(self, output_dir: str | Path = "data/p5/dataset") -> None:
        self.output_dir = Path(output_dir)
        self.hashes: dict[str, set[int]] = {"train": set(), "val": set(), "test": set()}
        self.stats: dict[str, int] = defaultdict(int)
        self.class_counts: dict[str, dict[str, int]] = {
            "train": defaultdict(int),
            "val": defaultdict(int),
            "test": defaultdict(int),
        }

    def _remap_label_content(self, raw_text: str, class_map: dict[int, int]) -> str:
        """Remap class IDs and discard classes outside target ontology."""
        remapped_lines = []
        for line in raw_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                raw_cls = int(parts[0])
                if raw_cls in class_map:
                    target_cls = class_map[raw_cls]
                    remapped_lines.append(f"{target_cls} {' '.join(parts[1:])}")
            except ValueError:
                continue
        return "\n".join(remapped_lines)

    def process_zip_source(
        self,
        zip_path: str | Path,
        class_map: dict[int, int],
        source_name: str,
        max_images_per_split: int | None = None,
    ) -> None:
        """Process images and labels from a zip archive."""
        zip_path = Path(zip_path)
        if not zip_path.exists():
            logger.warning("Source archive not found: %s", zip_path)
            return

        logger.info("Processing %s (%s)...", source_name, zip_path.name)
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = set(zf.namelist())

            # Find image entries
            image_entries = [
                n for n in zf.namelist()
                if n.lower().endswith((".jpg", ".jpeg", ".png")) and "/images/" in n
            ]

            split_counts = defaultdict(int)

            for img_name in image_entries:
                # Determine split
                split = "train"
                if "/valid/" in img_name or "/val/" in img_name:
                    split = "val"
                elif "/test/" in img_name:
                    split = "test"

                if max_images_per_split and split_counts[split] >= max_images_per_split:
                    continue

                # Locate corresponding label file
                lbl_name = img_name.replace("/images/", "/labels/")
                lbl_name = str(Path(lbl_name).with_suffix(".txt")).replace("\\", "/")

                if lbl_name not in namelist:
                    continue

                # Read and remap label
                raw_label = zf.read(lbl_name).decode("utf-8", errors="ignore")
                remapped_label = self._remap_label_content(raw_label, class_map)
                if not remapped_label.strip():
                    # No target classes present in this image
                    continue

                # Read image and compute hash
                img_bytes = zf.read(img_name)
                try:
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    img_hash = compute_dhash(pil_img)
                except Exception:
                    continue

                # Check for near-identical duplicate across all splits
                is_duplicate = False
                for _existing_split, hash_set in self.hashes.items():
                    for existing_h in hash_set:
                        if hamming_distance(img_hash, existing_h) <= 2:
                            is_duplicate = True
                            self.stats["duplicates_dropped"] += 1
                            break
                    if is_duplicate:
                        break

                if is_duplicate:
                    continue

                # Register hash
                self.hashes[split].add(img_hash)
                split_counts[split] += 1
                self.stats[f"{split}_saved"] += 1

                # Save standardized image & label
                stem = f"{source_name}_{Path(img_name).stem}"
                out_img_dir = self.output_dir / "images" / split
                out_lbl_dir = self.output_dir / "labels" / split
                out_img_dir.mkdir(parents=True, exist_ok=True)
                out_lbl_dir.mkdir(parents=True, exist_ok=True)

                out_img_path = out_img_dir / f"{stem}.jpg"
                out_lbl_path = out_lbl_dir / f"{stem}.txt"

                # Save JPEG
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                pil_img.save(out_img_path, format="JPEG", quality=90)

                # Save label
                with open(out_lbl_path, "w", encoding="utf-8") as f:
                    f.write(remapped_label + "\n")

                # Track class frequencies
                for line in remapped_label.split("\n"):
                    if line.strip():
                        c_id = int(line.split()[0])
                        c_name = TARGET_CLASSES.get(c_id, f"cls_{c_id}")
                        self.class_counts[split][c_name] += 1

    def write_dataset_yaml(self) -> Path:
        """Write official YOLO dataset YAML config."""
        yaml_content = {
            "path": str(self.output_dir.resolve()).replace("\\", "/"),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(TARGET_CLASSES),
            "names": [TARGET_CLASSES[i] for i in range(len(TARGET_CLASSES))],
        }
        yaml_path = self.output_dir / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_content, f, sort_keys=False)
        return yaml_path


def run_pipeline() -> None:
    """Execute end-to-end dataset preparation and deduplication."""
    preparer = DatasetPreparer(output_dir="data/p5/dataset")

    # Process Source 1: Construction Site Safety
    preparer.process_zip_source(
        zip_path="kaggle datasets/archive.zip",
        class_map=ARCHIVE_1_MAP,
        source_name="css",
        max_images_per_split=1500,
    )

    # Process Source 2: Personal Protective Equipment Dataset
    preparer.process_zip_source(
        zip_path="kaggle datasets/archive (1).zip",
        class_map=ARCHIVE_2_MAP,
        source_name="ppe",
        max_images_per_split=1500,
    )

    yaml_path = preparer.write_dataset_yaml()

    print("\n" + "=" * 60)
    print("DATASET PREPARATION & DEDUPLICATION REPORT")
    print("=" * 60)
    print(f"Dataset YAML: {yaml_path}")
    print(f"Duplicates dropped via dHash: {preparer.stats['duplicates_dropped']}")
    print(f"Train images: {preparer.stats['train_saved']}")
    print(f"Val images:   {preparer.stats['val_saved']}")
    print(f"Test images:  {preparer.stats['test_saved']}")
    print("\nClass Distribution:")
    for split in ["train", "val", "test"]:
        print(f"  [{split.upper()}]:")
        for cls_name, count in sorted(preparer.class_counts[split].items()):
            print(f"    - {cls_name:12s}: {count:5d} boxes")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
