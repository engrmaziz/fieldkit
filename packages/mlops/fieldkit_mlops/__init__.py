"""Fieldkit MLOps package: dataset manifests, anomaly training, evaluation, thresholds, and registry."""

from fieldkit_mlops.thresholds import (
    CostMatrixConfig,
    DecisionMetrics,
    ThresholdOptimizationResult,
    evaluate_decision_cost,
    optimize_inspection_thresholds,
)

__version__ = "0.1.0"
__all__ = [
    "CostMatrixConfig",
    "DecisionMetrics",
    "ThresholdOptimizationResult",
    "evaluate_decision_cost",
    "optimize_inspection_thresholds",
]
