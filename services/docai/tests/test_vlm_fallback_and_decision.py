"""Unit tests for VLM fallback, confidence fusion, and routing decision engine (P4 M3)."""

from __future__ import annotations

import numpy as np
import pytest
from fieldkit_docai.delivery.decision import (
    DeliveryDecisionEngine,
    tune_threshold_tau,
)
from fieldkit_docai.delivery.donut_infer import (
    DeliveryNoteFields,
    DonutExtractionResult,
    LineItemField,
)
from fieldkit_docai.delivery.validators import (
    DeliveryNoteValidator,
    MockPurchaseOrderRegistry,
)
from fieldkit_docai.delivery.vlm_fallback import MockVLMFallbackClient


@pytest.fixture
def registry() -> MockPurchaseOrderRegistry:
    reg = MockPurchaseOrderRegistry()
    reg.register_po(
        po_number="PO-2026-0412",
        supplier_name="Knorr Hydraulik GmbH",
        order_date="2026-04-10",
        allowed_parts=["PART-0104", "PART-0219"],
    )
    return reg


@pytest.fixture
def validator(registry: MockPurchaseOrderRegistry) -> DeliveryNoteValidator:
    return DeliveryNoteValidator(po_registry=registry)


@pytest.fixture
def vlm_client() -> MockVLMFallbackClient:
    return MockVLMFallbackClient()


@pytest.fixture
def engine(validator: DeliveryNoteValidator, vlm_client: MockVLMFallbackClient) -> DeliveryDecisionEngine:
    return DeliveryDecisionEngine(
        validator=validator,
        vlm_client=vlm_client,
        tau=0.85,
    )


def test_auto_accept_on_high_confidence_and_valid(engine: DeliveryDecisionEngine) -> None:
    """Verify Donut candidate with confidence >= tau and passing validators is auto-accepted."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    donut_res = DonutExtractionResult(
        fields=DeliveryNoteFields(
            supplier_name="Knorr Hydraulik GmbH",
            po_number="PO-2026-0412",
            delivery_date="2026-04-15",
            line_items=[LineItemField(part_no="PART-0104", description="Ventil", qty=10, unit="STK")],
            total_qty=10,
        ),
        confidence=0.96,  # >= 0.85
        raw_sequence="<s_delivery_note>...</s_delivery_note>",
        execution_time_sec=0.05,
    )

    decision = engine.evaluate(image=img, donut_result=donut_res)

    assert decision.action == "auto_accept"
    assert decision.source == "donut"
    assert decision.requires_review is False
    assert decision.accepted_fields is not None
    assert decision.accepted_fields.delivery_date == "2026-04-15"


def test_trigger_vlm_fallback_on_low_confidence(
    engine: DeliveryDecisionEngine, vlm_client: MockVLMFallbackClient
) -> None:
    """Verify Donut candidate with confidence < tau triggers VLM fallback and accepts VLM result."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    donut_res = DonutExtractionResult(
        fields=DeliveryNoteFields(
            supplier_name="Knorr Hydraulik GmbH",
            po_number="PO-2026-0412",
            delivery_date="2026-04-15",
            line_items=[LineItemField(part_no="PART-0104", description="Ventil", qty=10, unit="STK")],
            total_qty=10,
        ),
        confidence=0.65,  # < 0.85 triggers fallback
        raw_sequence="...",
        execution_time_sec=0.05,
    )

    # Configure VLM to return valid fields
    vlm_client.set_mock_return(
        DeliveryNoteFields(
            supplier_name="Knorr Hydraulik GmbH",
            po_number="PO-2026-0412",
            delivery_date="2026-04-15",
            line_items=[LineItemField(part_no="PART-0104", description="Ventil", qty=10, unit="STK")],
            total_qty=10,
        )
    )

    decision = engine.evaluate(image=img, donut_result=donut_res)

    assert decision.action == "accept"
    assert decision.source == "vlm"
    assert decision.requires_review is False
    assert decision.accepted_fields is not None


def test_escalate_to_review_queue_if_both_fail(
    engine: DeliveryDecisionEngine, vlm_client: MockVLMFallbackClient
) -> None:
    """Verify escalation to review queue when both Donut and VLM fail validation."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    donut_res = DonutExtractionResult(
        fields=DeliveryNoteFields(
            supplier_name="Knorr Hydraulik GmbH",
            po_number="PO-NONEXISTENT",  # Fails validator
            delivery_date="2026-04-15",
            line_items=[LineItemField(part_no="PART-0104", description="Ventil", qty=10, unit="STK")],
            total_qty=10,
        ),
        confidence=0.95,
        raw_sequence="...",
        execution_time_sec=0.05,
    )

    # VLM also fails
    vlm_client.set_mock_return(
        DeliveryNoteFields(
            supplier_name="Unknown Supplier",
            po_number="PO-NONEXISTENT",
            delivery_date="2026-04-15",
            line_items=[LineItemField(part_no="PART-0104", description="Ventil", qty=10, unit="STK")],
            total_qty=10,
        )
    )

    decision = engine.evaluate(image=img, donut_result=donut_res)

    assert decision.action == "escalate"
    assert decision.source == "review_queue"
    assert decision.requires_review is True
    assert decision.donut_candidate is not None
    assert decision.vlm_candidate is not None
    assert len(decision.failing_rules) > 0


def test_tune_threshold_tau() -> None:
    """Verify tuning threshold tau on validation set to achieve precision >= 0.99."""
    # Synthetic validation set: tuples of (confidence, is_ground_truth_correct, passes_validators)
    val_samples = [
        # High confidence, correct, valid
        (0.98, True, True),
        (0.95, True, True),
        (0.92, True, True),
        (0.89, True, True),
        (0.86, True, True),
        # Medium confidence, incorrect, but accidentally passes validators
        (0.75, False, True),
        (0.70, False, True),
        # Low confidence
        (0.55, False, False),
        (0.40, False, False),
    ]

    best_tau, precision, auto_accept_rate = tune_threshold_tau(
        val_samples, target_precision=0.99
    )

    assert best_tau >= 0.85
    assert precision >= 0.99
    assert auto_accept_rate > 0.0
