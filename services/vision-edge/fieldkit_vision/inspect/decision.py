"""Pure deterministic decision engine fusing anomaly localization and defect classification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from fieldkit_mlops.thresholds import CostMatrixConfig

from fieldkit_vision.inspect.anomaly import AnomalyResult
from fieldkit_vision.inspect.classifier import DefectPrediction
from fieldkit_vision.inspect.preprocess import PreprocessResult


class DecisionAction(StrEnum):
    """Disposition decision for inspected manufacturing component."""

    PASS = "pass"
    REJECT = "reject"
    REVIEW = "review"


class DecisionReason(StrEnum):
    """Deterministic rationale explaining the disposition verdict."""

    VERIFIED_CLEAN = "verified_clean"
    CONFIRMED_DEFECT = "confirmed_defect"
    BORDERLINE_ANOMALY = "borderline_anomaly"
    LOW_CONFIDENCE_CLASSIFICATION = "low_confidence_classification"
    ALIGNMENT_FAULT = "alignment_fault"
    RANDOM_AUDIT = "random_audit"


@dataclass
class InspectionDecision:
    """Final decision output for plant PLC or operator review dispatch."""

    action: DecisionAction
    reason: DecisionReason
    anomaly_score: float
    defect_class: str
    confidence: float
    estimated_cost: float
    is_audit_sample: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class InspectionDecisionEngine:
    """Deterministic routing state machine minimizing manufacturing escape and scrap costs."""

    def __init__(
        self,
        threshold_pass: float = 0.35,
        threshold_reject: float = 0.65,
        threshold_classifier_conf: float = 0.85,
        audit_rate: float = 0.02,
        cost_matrix: CostMatrixConfig | None = None,
    ) -> None:
        self.threshold_pass = threshold_pass
        self.threshold_reject = threshold_reject
        self.threshold_classifier_conf = threshold_classifier_conf
        self.audit_rate = audit_rate
        self.cost_matrix = cost_matrix or CostMatrixConfig()

    def evaluate(
        self,
        prep_result: PreprocessResult,
        anomaly_result: AnomalyResult,
        defect_prediction: DefectPrediction,
        item_id: str | None = None,
    ) -> InspectionDecision:
        """Evaluate preprocessed sample, anomaly score, and defect class against decision thresholds."""
        # 1. Geometric alignment fault gate
        if prep_result.is_misaligned or not prep_result.aligned:
            return InspectionDecision(
                action=DecisionAction.REVIEW,
                reason=DecisionReason.ALIGNMENT_FAULT,
                anomaly_score=anomaly_result.anomaly_score,
                defect_class=defect_prediction.predicted_class,
                confidence=defect_prediction.confidence,
                estimated_cost=self.cost_matrix.cost_review,
                is_audit_sample=False,
                details={
                    "inliers": prep_result.inlier_count,
                    "fault": "homography_alignment_failure",
                },
            )

        # 2. Defect classifier check
        is_classified_defect = (
            defect_prediction.is_defect and defect_prediction.predicted_class != "good"
        )
        if is_classified_defect:
            if defect_prediction.confidence >= self.threshold_classifier_conf:
                return InspectionDecision(
                    action=DecisionAction.REJECT,
                    reason=DecisionReason.CONFIRMED_DEFECT,
                    anomaly_score=anomaly_result.anomaly_score,
                    defect_class=defect_prediction.predicted_class,
                    confidence=defect_prediction.confidence,
                    estimated_cost=0.0,
                    is_audit_sample=False,
                    details={"source": "classifier_confirmed", "class": defect_prediction.predicted_class},
                )
            # Low confidence defect prediction routes to review
            return InspectionDecision(
                action=DecisionAction.REVIEW,
                reason=DecisionReason.LOW_CONFIDENCE_CLASSIFICATION,
                anomaly_score=anomaly_result.anomaly_score,
                defect_class=defect_prediction.predicted_class,
                confidence=defect_prediction.confidence,
                estimated_cost=self.cost_matrix.cost_review,
                is_audit_sample=False,
                details={"confidence": defect_prediction.confidence, "min_required": self.threshold_classifier_conf},
            )

        # 3. High-confidence Anomaly Rejection
        if anomaly_result.anomaly_score > self.threshold_reject:
            return InspectionDecision(
                action=DecisionAction.REJECT,
                reason=DecisionReason.CONFIRMED_DEFECT,
                anomaly_score=anomaly_result.anomaly_score,
                defect_class=defect_prediction.predicted_class,
                confidence=defect_prediction.confidence,
                estimated_cost=0.0,
                is_audit_sample=False,
                details={"source": "patchcore_anomaly_reject", "score": anomaly_result.anomaly_score},
            )

        # 4. Borderline Anomaly Grey-Zone [T_pass, T_reject]
        if anomaly_result.anomaly_score >= self.threshold_pass:
            return InspectionDecision(
                action=DecisionAction.REVIEW,
                reason=DecisionReason.BORDERLINE_ANOMALY,
                anomaly_score=anomaly_result.anomaly_score,
                defect_class=defect_prediction.predicted_class,
                confidence=defect_prediction.confidence,
                estimated_cost=self.cost_matrix.cost_review,
                is_audit_sample=False,
                details={
                    "score": anomaly_result.anomaly_score,
                    "range": f"[{self.threshold_pass}, {self.threshold_reject}]",
                },
            )

        # 5. Clean Component (Pass with 2% Random Audit Sampling)
        clean_seed = item_id or f"{anomaly_result.anomaly_score:.6f}_{defect_prediction.confidence:.6f}"
        digest = hashlib.sha256(clean_seed.encode("utf-8")).hexdigest()
        hash_val = int(digest[:8], 16) % 10000

        is_audit = hash_val < int(self.audit_rate * 10000)

        if is_audit:
            return InspectionDecision(
                action=DecisionAction.REVIEW,
                reason=DecisionReason.RANDOM_AUDIT,
                anomaly_score=anomaly_result.anomaly_score,
                defect_class="good",
                confidence=defect_prediction.confidence,
                estimated_cost=self.cost_matrix.cost_review,
                is_audit_sample=True,
                details={"audit_rate": self.audit_rate, "hash_sample": hash_val},
            )

        return InspectionDecision(
            action=DecisionAction.PASS,
            reason=DecisionReason.VERIFIED_CLEAN,
            anomaly_score=anomaly_result.anomaly_score,
            defect_class="good",
            confidence=defect_prediction.confidence,
            estimated_cost=0.0,
            is_audit_sample=False,
            details={"verdict": "pass_verified"},
        )
