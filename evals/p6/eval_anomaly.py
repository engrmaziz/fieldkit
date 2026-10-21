"""Evaluation module for unsupervised PatchCore anomaly baselines across MVTec AD categories."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from fieldkit_mlops.evaluate import (
    compute_image_auroc,
    compute_pixel_auroc,
    compute_pro_score,
)
from fieldkit_mlops.train_anomaly import train_patchcore_model
from fieldkit_vision.inspect.anomaly import PatchCoreAnomalyDetector

from evals.p6.dataset import MVTecSample, get_mvtec_benchmark_dataset

logger = logging.getLogger("fieldkit.evals.p6.anomaly")


@dataclass
class CategoryAnomalyMetrics:
    category: str
    total_samples: int
    image_auroc: float
    pixel_auroc: float
    pro_score: float
    avg_latency_ms: float
    p95_latency_ms: float
    coreset_size: int
    passed_gate: bool


@dataclass
class AnomalyBaselineReport:
    categories: list[CategoryAnomalyMetrics] = field(default_factory=list)
    mean_image_auroc: float = 0.0
    mean_pixel_auroc: float = 0.0
    mean_pro_score: float = 0.0
    overall_p95_latency_ms: float = 0.0
    all_categories_passed: bool = False


def evaluate_anomaly_baselines(
    dataset: dict[str, list[MVTecSample]] | None = None,
) -> AnomalyBaselineReport:
    """Execute PatchCore baseline benchmarks across MVTec AD categories."""
    if dataset is None:
        dataset = get_mvtec_benchmark_dataset()

    cat_metrics_list: list[CategoryAnomalyMetrics] = []
    all_latencies: list[float] = []

    for cat_name, samples in dataset.items():
        # Train baseline on normal/good samples for category
        good_imgs = [s.image for s in samples if not s.is_anomaly]
        bundle = train_patchcore_model(normal_images=good_imgs, category=cat_name, coreset_ratio=0.15)
        detector = PatchCoreAnomalyDetector(bundle=bundle, category=cat_name, patch_size=16, stride=16)

        y_true: list[int] = []
        y_scores: list[float] = []
        masks_true = []
        heatmaps_pred = []
        latencies = []

        for s in samples:
            res = detector.predict(s.image)
            y_true.append(1 if s.is_anomaly else 0)
            y_scores.append(res.anomaly_score)
            masks_true.append(s.mask)
            heatmaps_pred.append(res.heatmap)
            latencies.append(res.inference_ms)
            all_latencies.append(res.inference_ms)

        img_auroc = compute_image_auroc(y_true, y_scores)
        pix_auroc = compute_pixel_auroc(masks_true, heatmaps_pred)
        pro = compute_pro_score(masks_true, heatmaps_pred)

        latencies.sort()
        avg_lat = float(sum(latencies) / len(latencies)) if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = latencies[p95_idx] if latencies else 0.0

        passed = bool(img_auroc >= 0.95 and p95_lat < 100.0)

        cat_metrics_list.append(
            CategoryAnomalyMetrics(
                category=cat_name,
                total_samples=len(samples),
                image_auroc=round(img_auroc, 4),
                pixel_auroc=round(pix_auroc, 4),
                pro_score=round(pro, 4),
                avg_latency_ms=round(avg_lat, 2),
                p95_latency_ms=round(p95_lat, 2),
                coreset_size=len(detector.coreset),
                passed_gate=passed,
            )
        )

    all_latencies.sort()
    all_p95 = all_latencies[int(len(all_latencies) * 0.95)] if all_latencies else 0.0
    mean_img_auroc = float(sum(c.image_auroc for c in cat_metrics_list) / len(cat_metrics_list))
    mean_pix_auroc = float(sum(c.pixel_auroc for c in cat_metrics_list) / len(cat_metrics_list))
    mean_pro = float(sum(c.pro_score for c in cat_metrics_list) / len(cat_metrics_list))
    all_passed = all(c.passed_gate for c in cat_metrics_list)

    return AnomalyBaselineReport(
        categories=cat_metrics_list,
        mean_image_auroc=round(mean_img_auroc, 4),
        mean_pixel_auroc=round(mean_pix_auroc, 4),
        mean_pro_score=round(mean_pro, 4),
        overall_p95_latency_ms=round(all_p95, 2),
        all_categories_passed=all_passed,
    )
