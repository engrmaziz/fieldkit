"""Evaluation module for supervised defect classifier on NEU steel surface dataset."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from fieldkit_mlops.evaluate import (
    ClassificationReport,
    compute_calibration_error,
    compute_classification_metrics,
)
from fieldkit_vision.inspect.classifier import DefectClassifier

from evals.p6.dataset import NEU_CLASSES, NEUSample, get_neu_benchmark_dataset

logger = logging.getLogger("fieldkit.evals.p6.classifier")


@dataclass
class ClassifierEvaluationResult:
    total_samples: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    expected_calibration_error: float
    avg_latency_ms: float
    p95_latency_ms: float
    report: ClassificationReport
    passed_gate: bool


def evaluate_defect_classifier(
    samples: list[NEUSample] | None = None,
) -> ClassifierEvaluationResult:
    """Execute evaluation benchmark for calibrated defect classification."""
    if samples is None:
        samples = get_neu_benchmark_dataset()

    classifier = DefectClassifier(classes=NEU_CLASSES)

    y_true: list[int] = []
    y_pred: list[int] = []
    all_probas: list[list[float]] = []
    latencies: list[float] = []

    for s in samples:
        pred = classifier.predict(s.image)
        pred_idx = NEU_CLASSES.index(pred.predicted_class)
        y_true.append(s.class_idx)
        y_pred.append(pred_idx)
        probs_row = [pred.calibrated_probabilities[c] for c in NEU_CLASSES]
        all_probas.append(probs_row)
        latencies.append(pred.inference_ms)

    cls_report = compute_classification_metrics(y_true, y_pred, NEU_CLASSES)
    ece = compute_calibration_error(y_true, np.array(all_probas))

    latencies.sort()
    avg_lat = float(sum(latencies) / len(latencies)) if latencies else 0.0
    p95_idx = int(len(latencies) * 0.95)
    p95_lat = latencies[p95_idx] if latencies else 0.0

    passed = bool(cls_report.macro_f1 >= 0.95 and ece < 0.05 and p95_lat < 50.0)

    return ClassifierEvaluationResult(
        total_samples=len(samples),
        accuracy=round(cls_report.accuracy, 4),
        macro_precision=round(cls_report.macro_precision, 4),
        macro_recall=round(cls_report.macro_recall, 4),
        macro_f1=round(cls_report.macro_f1, 4),
        expected_calibration_error=round(ece, 4),
        avg_latency_ms=round(avg_lat, 2),
        p95_latency_ms=round(p95_lat, 2),
        report=cls_report,
        passed_gate=passed,
    )
