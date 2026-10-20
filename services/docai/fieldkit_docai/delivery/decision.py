"""Routing decision engine, confidence fusion, and threshold tuning (P4 M3).

Rules:
1. If Donut confidence >= tau and all validators pass:
   -> auto_accept (source="donut")
2. Else:
   -> Call VLM fallback (qwen2.5vl:7b) with page image + JSON schema
   -> Re-run deterministic validators on VLM output
   -> If VLM passes:
      -> accept (source="vlm")
   -> Else:
      -> escalate to review_queue with both candidates and failing validator rules
3. tune_threshold_tau:
   -> Sweeps candidate thresholds on validation set to achieve auto-accept precision >= target_precision (0.99).
"""

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from fieldkit_common.logging import get_logger
from PIL import Image

from fieldkit_docai.delivery.donut_infer import DeliveryNoteFields, DonutExtractionResult
from fieldkit_docai.delivery.validators import DeliveryNoteValidator, ValidationResult
from fieldkit_docai.delivery.vlm_fallback import VLMFallbackClient

logger = get_logger("fieldkit.docai.delivery.decision")


@dataclass
class DeliveryDecision:
    action: str  # "auto_accept" | "accept" | "escalate"
    source: str  # "donut" | "vlm" | "review_queue"
    requires_review: bool
    accepted_fields: DeliveryNoteFields | None = None
    donut_candidate: DeliveryNoteFields | None = None
    vlm_candidate: DeliveryNoteFields | None = None
    failing_rules: list[str] = field(default_factory=list)
    donut_confidence: float = 0.0
    vlm_confidence: float | None = None
    latency_sec: float = 0.0
    validation_details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "source": self.source,
            "requires_review": self.requires_review,
            "accepted_fields": self.accepted_fields.model_dump() if self.accepted_fields else None,
            "donut_candidate": self.donut_candidate.model_dump() if self.donut_candidate else None,
            "vlm_candidate": self.vlm_candidate.model_dump() if self.vlm_candidate else None,
            "failing_rules": self.failing_rules,
            "donut_confidence": round(self.donut_confidence, 4),
            "vlm_confidence": round(self.vlm_confidence, 4) if self.vlm_confidence is not None else None,
            "latency_sec": round(self.latency_sec, 4),
            "validation_details": self.validation_details,
        }


class DeliveryDecisionEngine:
    """Confidence fusion and decision routing engine with VLM fallback."""

    def __init__(
        self,
        validator: DeliveryNoteValidator,
        vlm_client: VLMFallbackClient | None = None,
        tau: float = 0.85,
    ) -> None:
        self.validator = validator
        self.vlm_client = vlm_client or VLMFallbackClient()
        self.tau = tau

    def evaluate(
        self,
        image: np.ndarray | Image.Image,
        donut_result: DonutExtractionResult,
        ocr_hint: str | None = None,
    ) -> DeliveryDecision:
        """Evaluate Donut extraction and route to auto-accept, VLM fallback, or review queue."""
        t_start = time.perf_counter()

        # Step 1: Run deterministic validators on Donut output
        donut_val: ValidationResult = self.validator.validate(donut_result.fields)

        # Step 2: High confidence + passed validation -> AUTO ACCEPT
        if donut_result.confidence >= self.tau and donut_val.is_valid:
            latency = time.perf_counter() - t_start + donut_result.execution_time_sec
            logger.info("delivery_auto_accepted", confidence=donut_result.confidence, tau=self.tau)
            return DeliveryDecision(
                action="auto_accept",
                source="donut",
                requires_review=False,
                accepted_fields=donut_result.fields,
                donut_candidate=donut_result.fields,
                donut_confidence=donut_result.confidence,
                latency_sec=latency,
            )

        # Step 3: Trigger VLM Fallback
        logger.info(
            "triggering_vlm_fallback",
            confidence=donut_result.confidence,
            donut_valid=donut_val.is_valid,
            failing_rules=donut_val.failed_rules,
        )
        vlm_fields, vlm_conf, vlm_latency = self.vlm_client.extract_fields(
            image=image, prompt_hint=ocr_hint
        )
        vlm_val: ValidationResult = self.validator.validate(vlm_fields)

        # Step 4: If VLM passes validation -> ACCEPT
        if vlm_val.is_valid:
            total_latency = time.perf_counter() - t_start + donut_result.execution_time_sec
            logger.info("vlm_fallback_accepted", confidence=vlm_conf)
            return DeliveryDecision(
                action="accept",
                source="vlm",
                requires_review=False,
                accepted_fields=vlm_fields,
                donut_candidate=donut_result.fields,
                vlm_candidate=vlm_fields,
                donut_confidence=donut_result.confidence,
                vlm_confidence=vlm_conf,
                latency_sec=total_latency,
            )

        # Step 5: Both failed -> ESCALATE TO REVIEW QUEUE
        total_latency = time.perf_counter() - t_start + donut_result.execution_time_sec
        combined_failures = list(dict.fromkeys(donut_val.failed_rules + vlm_val.failed_rules))
        logger.warning(
            "delivery_escalated_to_review_queue",
            failing_rules=combined_failures,
        )
        return DeliveryDecision(
            action="escalate",
            source="review_queue",
            requires_review=True,
            accepted_fields=None,
            donut_candidate=donut_result.fields,
            vlm_candidate=vlm_fields,
            failing_rules=combined_failures,
            donut_confidence=donut_result.confidence,
            vlm_confidence=vlm_conf,
            latency_sec=total_latency,
            validation_details={
                "donut_details": donut_val.details,
                "vlm_details": vlm_val.details,
            },
        )


def tune_threshold_tau(
    val_samples: list[tuple[float, bool, bool]],
    target_precision: float = 0.99,
) -> tuple[float, float, float]:
    """Sweep thresholds tau on validation samples to maximize auto-accept rate while precision >= target.

    Args:
        val_samples: List of (confidence, is_correct, passes_validators) tuples.
        target_precision: Minimum required precision for auto-accepted records (default: 0.99).

    Returns:
        (best_tau, precision_at_tau, auto_accept_rate_at_tau)
    """
    if not val_samples:
        return 0.85, 1.0, 0.0

    total_n = len(val_samples)
    best_tau = 0.99
    best_precision = 1.0
    best_rate = 0.0

    # Test thresholds from 0.50 to 0.99 with step 0.01
    candidate_taus = [round(t * 0.01, 2) for t in range(50, 100)]

    for tau in candidate_taus:
        accepted = [
            (corr, valid)
            for conf, corr, valid in val_samples
            if conf >= tau and valid
        ]
        if not accepted:
            continue

        n_accepted = len(accepted)
        n_correct = sum(1 for corr, _ in accepted if corr)
        precision = n_correct / n_accepted
        rate = n_accepted / total_n

        if precision >= target_precision:
            # We want the lowest tau that satisfies precision to maximize auto-accept rate
            if rate >= best_rate:
                best_tau = tau
                best_precision = precision
                best_rate = rate

    return best_tau, best_precision, best_rate
