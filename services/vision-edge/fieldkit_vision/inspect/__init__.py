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
from fieldkit_vision.inspect.models import (
    InspectionRecord,
    InspectionRequest,
    InspectionResponse,
    InspectionReviewUpdate,
)
from fieldkit_vision.inspect.preprocess import InspectionPreprocessor, PreprocessResult
from fieldkit_vision.inspect.router import router as inspect_router
from fieldkit_vision.inspect.shadow import (
    PairedShadowRecord,
    ShadowInspectionManager,
    ShadowPromotionReport,
)
from fieldkit_vision.inspect.storage import HeatmapStorageManager
from fieldkit_vision.inspect.worker import InspectionWorker

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
    "InspectionRequest",
    "InspectionResponse",
    "InspectionRecord",
    "InspectionReviewUpdate",
    "HeatmapStorageManager",
    "InspectionWorker",
    "PairedShadowRecord",
    "ShadowInspectionManager",
    "ShadowPromotionReport",
    "inspect_router",
]
