"""Unsupervised PatchCore anomaly model training and greedy k-Center coreset subsampling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("fieldkit.mlops.anomaly")


def greedy_k_center(
    features: np.ndarray,
    coreset_ratio: float = 0.10,
    seed: int = 42,
) -> np.ndarray:
    """Subsample feature memory bank via greedy k-Center clustering.

    Minimizes the maximum distance from any training feature to the closest coreset center:
        min_{C} max_{x in X} min_{c in C} ||x - c||_2
    """
    n_samples = len(features)
    n_coreset = max(1, int(n_samples * coreset_ratio))

    if n_coreset >= n_samples:
        return features

    rng = np.random.RandomState(seed)
    first_idx = int(rng.randint(0, n_samples))

    selected_indices = [first_idx]
    # Initialize distances to first center
    min_distances = np.linalg.norm(features - features[first_idx], axis=1)

    for _ in range(1, n_coreset):
        # Select point with maximum distance to existing centers
        new_center_idx = int(np.argmax(min_distances))
        selected_indices.append(new_center_idx)

        # Update minimum distances
        new_distances = np.linalg.norm(features - features[new_center_idx], axis=1)
        min_distances = np.minimum(min_distances, new_distances)

    return features[selected_indices]


def extract_patch_features(
    image: np.ndarray,
    patch_size: int = 16,
    stride: int = 8,
) -> tuple[np.ndarray, tuple[int, int]]:
    """Extract multi-channel texture and edge patch descriptors across spatial 2D grid."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray = image.astype(np.float32)

    # Compute horizontal and vertical gradients (Sobel)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    lap = cv2.Laplacian(gray, cv2.CV_32F)

    # Extract sliding window patches
    w_g = np.lib.stride_tricks.sliding_window_view(gray, (patch_size, patch_size))[::stride, ::stride]
    w_m = np.lib.stride_tricks.sliding_window_view(mag, (patch_size, patch_size))[::stride, ::stride]
    w_l = np.lib.stride_tricks.sliding_window_view(lap, (patch_size, patch_size))[::stride, ::stride]

    grid_h, grid_w = w_g.shape[:2]
    area = patch_size * patch_size
    p_g = w_g.reshape(-1, area)
    p_m = w_m.reshape(-1, area)
    p_l = w_l.reshape(-1, area)

    # Compute vectorized 12-dimensional statistical and edge descriptors
    features = np.hstack(
        [
            np.mean(p_g, axis=1, keepdims=True),
            np.std(p_g, axis=1, keepdims=True),
            np.min(p_g, axis=1, keepdims=True),
            np.max(p_g, axis=1, keepdims=True),
            np.mean(p_m, axis=1, keepdims=True),
            np.std(p_m, axis=1, keepdims=True),
            np.max(p_m, axis=1, keepdims=True),
            np.mean(p_l, axis=1, keepdims=True),
            np.std(p_l, axis=1, keepdims=True),
            np.min(p_l, axis=1, keepdims=True),
            np.max(p_l, axis=1, keepdims=True),
            np.max(p_l, axis=1, keepdims=True) - np.min(p_l, axis=1, keepdims=True),
        ]
    )

    # L2 normalize descriptor vectors
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    features = features / np.maximum(norms, 1e-6)

    return features.astype(np.float32), (grid_h, grid_w)


@dataclass
class AnomalyModelBundle:
    category: str
    coreset_bank: np.ndarray  # (M, D)
    mean_baseline: float
    std_baseline: float
    threshold_pass: float
    threshold_reject: float
    parameters: dict[str, Any]

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            p,
            coreset_bank=self.coreset_bank,
            meta=np.array(
                [
                    self.category,
                    str(self.mean_baseline),
                    str(self.std_baseline),
                    str(self.threshold_pass),
                    str(self.threshold_reject),
                ]
            ),
        )

    @classmethod
    def load(cls, path: Path | str) -> AnomalyModelBundle:
        p = Path(path)
        data = np.load(p, allow_pickle=True)
        coreset_bank = data["coreset_bank"]
        meta = data["meta"]
        category = str(meta[0])
        mean_baseline = float(meta[1])
        std_baseline = float(meta[2])
        threshold_pass = float(meta[3])
        threshold_reject = float(meta[4])

        return cls(
            category=category,
            coreset_bank=coreset_bank,
            mean_baseline=mean_baseline,
            std_baseline=std_baseline,
            threshold_pass=threshold_pass,
            threshold_reject=threshold_reject,
            parameters={},
        )


def train_patchcore_model(
    normal_images: list[np.ndarray],
    category: str = "metal_nut",
    coreset_ratio: float = 0.10,
    threshold_pass: float = 0.38,
    threshold_reject: float = 0.65,
) -> AnomalyModelBundle:
    """Train unsupervised PatchCore anomaly baseline using normal/good training images only."""
    all_patches: list[np.ndarray] = []

    for img in normal_images:
        patches, _ = extract_patch_features(img, patch_size=16, stride=8)
        all_patches.append(patches)

    if not all_patches:
        raise ValueError("No patches extracted from normal training images")

    feature_bank = np.concatenate(all_patches, axis=0)
    logger.info("Category %s: Extracted %d patch features from %d images", category, len(feature_bank), len(normal_images))

    # Perform greedy k-Center subsampling
    coreset_bank = greedy_k_center(feature_bank, coreset_ratio=coreset_ratio)
    logger.info("Category %s: Subsampled to %d coreset centers (%.1f%%)", category, len(coreset_bank), coreset_ratio * 100)

    # Compute self-distances on normal images to calibrate baseline distribution
    sample_scores = []
    for img in normal_images[:10]:
        patches, _ = extract_patch_features(img, patch_size=16, stride=16)
        # Compute min distance to coreset
        dists = np.min(np.linalg.norm(patches[:, None, :] - coreset_bank[None, :, :], axis=2), axis=1)
        top_k = max(1, int(len(dists) * 0.02))
        top_dists = np.partition(dists, -top_k)[-top_k:]
        sample_scores.append(float(np.mean(top_dists)))

    mean_baseline = float(np.mean(sample_scores)) if sample_scores else 0.05
    std_baseline = float(np.std(sample_scores)) if sample_scores else 0.02

    return AnomalyModelBundle(
        category=category,
        coreset_bank=coreset_bank,
        mean_baseline=mean_baseline,
        std_baseline=std_baseline,
        threshold_pass=threshold_pass,
        threshold_reject=threshold_reject,
        parameters={"coreset_ratio": coreset_ratio, "patch_size": 16, "stride": 8},
    )
