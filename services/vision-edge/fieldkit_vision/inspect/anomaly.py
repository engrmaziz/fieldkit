"""Runtime PatchCore anomaly detector producing calibrated anomaly scores and 2D pixel heatmaps."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from fieldkit_mlops.train_anomaly import AnomalyModelBundle, extract_patch_features


@dataclass
class AnomalyResult:
    """Inference output from unsupervised anomaly detector."""

    anomaly_score: float
    is_anomaly: bool
    heatmap: np.ndarray  # (256, 256) float32 [0.0, 1.0]
    max_pixel_score: float
    inference_ms: float
    category: str = "generic"


class PatchCoreAnomalyDetector:
    """Production runtime for unsupervised defect anomaly localization and scoring."""

    def __init__(
        self,
        bundle: AnomalyModelBundle | None = None,
        bundle_path: Path | str | None = None,
        category: str = "metal_nut",
        threshold_pass: float = 0.38,
        threshold_reject: float = 0.65,
        patch_size: int = 16,
        stride: int = 8,
        heatmap_sigma: float = 4.0,
    ) -> None:
        self.category = category
        self.threshold_pass = threshold_pass
        self.threshold_reject = threshold_reject
        self.patch_size = patch_size
        self.stride = stride
        self.heatmap_sigma = heatmap_sigma

        if bundle is not None:
            self.bundle = bundle
        elif bundle_path is not None and Path(bundle_path).exists():
            self.bundle = AnomalyModelBundle.load(bundle_path)
        else:
            # Synthetic default baseline memory bank for turnkey execution
            self.bundle = self._create_default_bundle(category)

        self.coreset = self.bundle.coreset_bank

    def _create_default_bundle(self, category: str) -> AnomalyModelBundle:
        """Construct calibrated default memory bank for offline evaluation and testing."""
        rng = np.random.RandomState(42)
        # Synthetic baseline patch features: 150 centers with 12 dimensions
        coreset = rng.normal(loc=0.0, scale=0.3, size=(150, 12)).astype(np.float32)
        # L2 normalize
        norms = np.linalg.norm(coreset, axis=1, keepdims=True)
        coreset = coreset / np.maximum(norms, 1e-6)

        return AnomalyModelBundle(
            category=category,
            coreset_bank=coreset,
            mean_baseline=0.18,
            std_baseline=0.04,
            threshold_pass=self.threshold_pass,
            threshold_reject=self.threshold_reject,
            parameters={"synthetic": True},
        )

    def predict(self, image: np.ndarray) -> AnomalyResult:
        """Evaluate component image and return image-level anomaly score and 2D pixel heatmap."""
        t0 = time.perf_counter()

        # 1. Extract patch descriptors
        patches, (grid_h, grid_w) = extract_patch_features(image, patch_size=self.patch_size, stride=self.stride)

        # 2. Nearest-neighbor distances to coreset memory bank
        # patches: (N, D), coreset: (M, D)
        # Compute pairwise Euclidean distance matrix
        diffs = patches[:, None, :] - self.coreset[None, :, :]
        dist_matrix = np.linalg.norm(diffs, axis=2)  # (N, M)
        min_patch_dists = np.min(dist_matrix, axis=1)  # (N,)

        # 3. Spatial Heatmap Reconstruction
        patch_grid = min_patch_dists.reshape(grid_h, grid_w)
        h_orig, w_orig = image.shape[:2]

        # Bilinear upsample to image resolution
        heatmap = cv2.resize(patch_grid, (w_orig, h_orig), interpolation=cv2.INTER_LINEAR)

        # Gaussian smoothing to remove patch blockiness
        ksize = int(self.heatmap_sigma * 4) | 1  # ensure odd kernel size
        heatmap = cv2.GaussianBlur(heatmap, (ksize, ksize), sigmaX=self.heatmap_sigma)

        # 4. Score Normalization
        # Calibrate distance via exponential response function
        # When distance is close to normal baseline, score -> 0.0; defects saturate towards 1.0
        margin = max(0.0, float(self.bundle.mean_baseline + 2.0 * self.bundle.std_baseline))

        excess_heatmap = np.maximum(0.0, heatmap - margin)
        norm_heatmap = (1.0 - np.exp(-5.0 * excess_heatmap)).astype(np.float32)
        norm_heatmap = np.clip(norm_heatmap, 0.0, 1.0)

        # Top 2% patch distance weighting for image-level anomaly score
        top_k = max(1, int(len(min_patch_dists) * 0.02))
        top_dists = np.partition(min_patch_dists, -top_k)[-top_k:]
        raw_image_score = float(np.mean(top_dists))

        raw_excess = max(0.0, raw_image_score - margin)
        image_score = float(np.clip(1.0 - np.exp(-5.0 * raw_excess), 0.0, 1.0))
        is_anom = bool(image_score >= self.threshold_pass)

        t_elapsed = (time.perf_counter() - t0) * 1000.0

        return AnomalyResult(
            anomaly_score=round(image_score, 4),
            is_anomaly=is_anom,
            heatmap=norm_heatmap,
            max_pixel_score=float(np.max(norm_heatmap)),
            inference_ms=round(t_elapsed, 2),
            category=self.category,
        )

    @staticmethod
    def generate_heatmap_overlay(
        image: np.ndarray,
        heatmap: np.ndarray,
        alpha: float = 0.45,
    ) -> np.ndarray:
        """Blend pseudo-color Jet heatmap overlay over grayscale or RGB component image."""
        heat_u8 = (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8)
        color_map = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

        base_img = image.copy()
        if len(base_img.shape) == 2:
            base_img = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)

        blended = cv2.addWeighted(color_map, alpha, base_img, 1.0 - alpha, 0)
        return blended
