"""Defect inspection modules for Project 6 (InspectAI)."""

from fieldkit_vision.inspect.anomaly import AnomalyResult, PatchCoreAnomalyDetector
from fieldkit_vision.inspect.classifier import (
    DEFAULT_DEFECT_CLASSES,
    DefectClassifier,
    DefectPrediction,
)
from fieldkit_vision.inspect.decision import (
    DecisionAction,
    DecisionReason,
    InspectionDecision,
    InspectionDecisionEngine,
)
from fieldkit_vision.inspect.preprocess import InspectionPreprocessor, PreprocessResult

__version__ = "0.1.0"
__all__ = [
    "AnomalyResult",
    "PatchCoreAnomalyDetector",
    "DEFAULT_DEFECT_CLASSES",
    "DefectClassifier",
    "DefectPrediction",
    "DecisionAction",
    "DecisionReason",
    "InspectionDecision",
    "InspectionDecisionEngine",
    "InspectionPreprocessor",
    "PreprocessResult",
]
