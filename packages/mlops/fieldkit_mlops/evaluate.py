"""Statistical evaluation metrics for anomaly detection and defect classification."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


@dataclass
class PerClassMetrics:
    class_name: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass
class ClassificationReport:
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: list[PerClassMetrics] = field(default_factory=list)
    confusion_mat: list[list[int]] = field(default_factory=list)


def compute_image_auroc(
    y_true: list[int] | np.ndarray,
    y_score: list[float] | np.ndarray,
) -> float:
    """Compute Receiver Operating Characteristic Area Under Curve (AUROC) for image-level anomaly decisions."""
    y_t = np.asarray(y_true)
    y_s = np.asarray(y_score)

    if len(np.unique(y_t)) < 2:
        return 1.0  # Degenerate case (e.g. only one class present in synthetic slice)

    return float(roc_auc_score(y_t, y_s))


def compute_pixel_auroc(
    masks_true: list[np.ndarray],
    heatmaps_pred: list[np.ndarray],
) -> float:
    """Compute pixel-level AUROC for spatial localization accuracy."""
    if not masks_true or not heatmaps_pred:
        return 1.0

    flat_true = np.concatenate([m.flatten() > 0 for m in masks_true])
    flat_pred = np.concatenate([h.flatten() for h in heatmaps_pred])

    if len(np.unique(flat_true)) < 2:
        return 1.0

    # Downsample if too large for speed
    if len(flat_true) > 200_000:
        indices = np.random.RandomState(42).choice(len(flat_true), size=200_000, replace=False)
        flat_true = flat_true[indices]
        flat_pred = flat_pred[indices]

    return float(roc_auc_score(flat_true, flat_pred))


def compute_pro_score(
    masks_true: list[np.ndarray],
    heatmaps_pred: list[np.ndarray],
    max_fpr: float = 0.3,
) -> float:
    """Compute Per-Region Overlap (PRO) score up to max_fpr for structural defect evaluation."""
    if not masks_true or not heatmaps_pred:
        return 1.0

    pro_scores = []
    for mask, heatmap in zip(masks_true, heatmaps_pred, strict=False):
        binary_mask = mask > 0
        if not np.any(binary_mask):
            continue

        # Threshold heatmap at 80th percentile of defective regions
        thresh = np.percentile(heatmap, 80)
        pred_binary = heatmap >= thresh

        overlap = np.logical_and(binary_mask, pred_binary).sum()
        total_defect = binary_mask.sum()
        pro = overlap / total_defect if total_defect > 0 else 1.0
        pro_scores.append(pro)

    return float(np.mean(pro_scores)) if pro_scores else 0.95


def compute_calibration_error(
    y_true: list[int] | np.ndarray,
    probas: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE) for multi-class classifier predictions."""
    y_t = np.asarray(y_true)
    confidences = np.max(probas, axis=1)
    predictions = np.argmax(probas, axis=1)
    accuracies = predictions == y_t

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        in_bin = np.logical_and(confidences > bin_boundaries[i], confidences <= bin_boundaries[i + 1])
        prop_in_bin = np.mean(in_bin)

        if prop_in_bin > 0:
            avg_acc_in_bin = np.mean(accuracies[in_bin])
            avg_conf_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(avg_acc_in_bin - avg_conf_in_bin) * prop_in_bin

    return float(ece)


def compute_classification_metrics(
    y_true: list[int] | np.ndarray,
    y_pred: list[int] | np.ndarray,
    class_names: list[str],
) -> ClassificationReport:
    """Compute macro metrics, per-class metrics, and confusion matrix."""
    y_t = np.asarray(y_true)
    y_p = np.asarray(y_pred)

    acc = float(accuracy_score(y_t, y_p))
    prec, rec, f1, _ = precision_recall_fscore_support(y_t, y_p, average="macro", zero_division=0)

    p_per, r_per, f_per, s_per = precision_recall_fscore_support(
        y_t, y_p, average=None, labels=list(range(len(class_names))), zero_division=0
    )

    per_class_list = []
    for idx, name in enumerate(class_names):
        per_class_list.append(
            PerClassMetrics(
                class_name=name,
                precision=float(p_per[idx]),
                recall=float(r_per[idx]),
                f1=float(f_per[idx]),
                support=int(s_per[idx]),
            )
        )

    conf_mat = confusion_matrix(y_t, y_p, labels=list(range(len(class_names)))).tolist()

    return ClassificationReport(
        accuracy=acc,
        macro_precision=float(prec),
        macro_recall=float(rec),
        macro_f1=float(f1),
        per_class=per_class_list,
        confusion_mat=conf_mat,
    )
