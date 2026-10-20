"""Unit tests for deterministic delivery note validators (P4 M3)."""

from __future__ import annotations

import pytest
from fieldkit_docai.delivery.donut_infer import DeliveryNoteFields, LineItemField
from fieldkit_docai.delivery.validators import (
    DeliveryNoteValidator,
    MockPurchaseOrderRegistry,
)


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


def test_valid_delivery_note_passes(validator: DeliveryNoteValidator) -> None:
    """Verify that a compliant delivery note passes all validation rules."""
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        supplier_address="Industriestrasse 14, 70565 Stuttgart",
        delivery_note_no="LS-2026-0012",
        po_number="PO-2026-0412",
        delivery_date="2026-04-18",  # Within 8 days of PO
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=20, unit="STK"),
            LineItemField(part_no="PART-0219", description="Wellendichtring", qty=10, unit="STK"),
        ],
        total_qty=30,  # 20 + 10 == 30
    )

    res = validator.validate(note)
    assert res.is_valid is True
    assert len(res.failed_rules) == 0
    assert "SUM_QUANTITIES_MATCH" in res.passed_rules
    assert "PO_EXISTS" in res.passed_rules
    assert "SUPPLIER_MATCH" in res.passed_rules
    assert "DATE_IN_WINDOW" in res.passed_rules
    assert "PARTS_EXIST" in res.passed_rules
    assert "QUANTITIES_POSITIVE" in res.passed_rules


def test_quantity_sum_mismatch_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that sum(item.qty) != total_qty triggers validation failure."""
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        po_number="PO-2026-0412",
        delivery_date="2026-04-18",
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=20, unit="STK"),
            LineItemField(part_no="PART-0219", description="Wellendichtring", qty=10, unit="STK"),
        ],
        total_qty=35,  # Mismatch: 30 != 35
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "SUM_QUANTITIES_MATCH" in res.failed_rules


def test_non_existent_po_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that non-existent PO reference triggers PO_EXISTS failure."""
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        po_number="PO-2026-9999",  # Does not exist
        delivery_date="2026-04-18",
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=10, unit="STK"),
        ],
        total_qty=10,
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "PO_EXISTS" in res.failed_rules


def test_supplier_mismatch_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that supplier mismatch between note and PO fails fuzzy match."""
    note = DeliveryNoteFields(
        supplier_name="Apex Precision Components Ltd",  # PO belongs to Knorr Hydraulik
        po_number="PO-2026-0412",
        delivery_date="2026-04-18",
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=10, unit="STK"),
        ],
        total_qty=10,
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "SUPPLIER_MATCH" in res.failed_rules


def test_delivery_date_outside_window_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that delivery date outside +-30 day PO window fails validation."""
    # PO date: 2026-04-10. > 30 days later: 2026-05-25 (45 days)
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        po_number="PO-2026-0412",
        delivery_date="2026-05-25",
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=10, unit="STK"),
        ],
        total_qty=10,
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "DATE_IN_WINDOW" in res.failed_rules


def test_unknown_part_number_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that an unknown part number triggers PARTS_EXIST failure."""
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        po_number="PO-2026-0412",
        delivery_date="2026-04-18",
        line_items=[
            LineItemField(part_no="PART-9999", description="Unrecognized Widget", qty=10, unit="STK"),
        ],
        total_qty=10,
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "PARTS_EXIST" in res.failed_rules


def test_zero_or_negative_quantity_fails(validator: DeliveryNoteValidator) -> None:
    """Verify that quantities <= 0 fail QUANTITIES_POSITIVE rule."""
    note = DeliveryNoteFields(
        supplier_name="Knorr Hydraulik GmbH",
        po_number="PO-2026-0412",
        delivery_date="2026-04-18",
        line_items=[
            LineItemField(part_no="PART-0104", description="Hydraulikventil", qty=0, unit="STK"),
        ],
        total_qty=0,
    )

    res = validator.validate(note)
    assert res.is_valid is False
    assert "QUANTITIES_POSITIVE" in res.failed_rules
