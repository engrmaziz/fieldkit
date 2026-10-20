"""Deterministic delivery note validators and ontology purchase order checks (P4 M3).

Rules enforced:
1. SUM_QUANTITIES_MATCH: sum(item.qty) == total_qty
2. PO_EXISTS: PO reference exists in ontology purchase order catalog
3. SUPPLIER_MATCH: Supplier name matches PO supplier (fuzzy match via normalized match_key)
4. DATE_IN_WINDOW: Delivery date within PO order window +-30 days
5. PARTS_EXIST: Part numbers exist in Halden components catalog
6. QUANTITIES_POSITIVE: Every line item has quantity > 0
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any

from fieldkit_er.normalize import normalize_name

from fieldkit_docai.delivery.donut_infer import DeliveryNoteFields

logger = logging.getLogger("fieldkit.docai.delivery.validators")

# Default Halden parts catalog
DEFAULT_PARTS_CATALOG = {
    "PART-0104",
    "PART-0219",
    "PART-0342",
    "PART-0488",
    "PART-0511",
    "PART-0673",
    "PART-0782",
    "PART-0899",
    "PART-0915",
    "PART-1024",
}


@dataclass
class PurchaseOrderRecord:
    po_number: str
    supplier_name: str
    order_date: str  # YYYY-MM-DD
    allowed_parts: set[str] = field(default_factory=set)


class MockPurchaseOrderRegistry:
    """In-memory ontology/ERP purchase order registry with known orders."""

    def __init__(self) -> None:
        self._registry: dict[str, PurchaseOrderRecord] = {}
        self._seed_default_orders()

    def _seed_default_orders(self) -> None:
        """Seed known purchase orders for testing and simulations."""
        self.register_po(
            po_number="PO-2026-0412",
            supplier_name="Knorr Hydraulik GmbH",
            order_date="2026-04-10",
            allowed_parts={"PART-0104", "PART-0219"},
        )
        self.register_po(
            po_number="PO-2026-0819",
            supplier_name="Halden Armaturen GmbH",
            order_date="2026-06-05",
            allowed_parts={"PART-0044", "PART-0104"},
        )
        self.register_po(
            po_number="PO-2026-4412",
            supplier_name="Halden Hydraulik GmbH",
            order_date="2026-05-10",
            allowed_parts={"PART-102", "PART-105"},
        )

    def register_po(
        self,
        po_number: str,
        supplier_name: str,
        order_date: str,
        allowed_parts: set[str] | list[str] | None = None,
    ) -> None:
        parts = set(allowed_parts) if allowed_parts else set()
        self._registry[po_number.upper().strip()] = PurchaseOrderRecord(
            po_number=po_number.upper().strip(),
            supplier_name=supplier_name.strip(),
            order_date=order_date.strip(),
            allowed_parts=parts,
        )

    def get_po(self, po_number: str) -> PurchaseOrderRecord | None:
        return self._registry.get(po_number.upper().strip())


@dataclass
class ValidationResult:
    is_valid: bool
    passed_rules: list[str] = field(default_factory=list)
    failed_rules: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "details": self.details,
        }


class DeliveryNoteValidator:
    """Deterministic validator verifying delivery notes against ERP ontology rules."""

    def __init__(
        self,
        po_registry: MockPurchaseOrderRegistry | None = None,
        parts_catalog: set[str] | None = None,
        date_window_days: int = 30,
    ) -> None:
        self.po_registry = po_registry or MockPurchaseOrderRegistry()
        self.parts_catalog = parts_catalog or DEFAULT_PARTS_CATALOG
        self.date_window_days = date_window_days

    def validate(self, note: DeliveryNoteFields) -> ValidationResult:
        passed: list[str] = []
        failed: list[str] = []
        details: dict[str, Any] = {}

        # 1. SUM_QUANTITIES_MATCH
        sum_items = sum(item.qty for item in note.line_items)
        if sum_items == note.total_qty and note.total_qty > 0:
            passed.append("SUM_QUANTITIES_MATCH")
        else:
            failed.append("SUM_QUANTITIES_MATCH")
            details["sum_mismatch"] = {
                "sum_line_items": sum_items,
                "declared_total": note.total_qty,
            }

        # 2. QUANTITIES_POSITIVE
        all_positive = len(note.line_items) > 0 and all(item.qty > 0 for item in note.line_items)
        if all_positive:
            passed.append("QUANTITIES_POSITIVE")
        else:
            failed.append("QUANTITIES_POSITIVE")
            details["non_positive_items"] = [
                item.model_dump() for item in note.line_items if item.qty <= 0
            ]

        # 3. PO_EXISTS & PO-Dependent Rules
        po_record = self.po_registry.get_po(note.po_number)
        if po_record is not None:
            passed.append("PO_EXISTS")

            # 4. SUPPLIER_MATCH (Fuzzy matching via normalized entity resolution keys)
            norm_note_sup = normalize_name(note.supplier_name)
            norm_po_sup = normalize_name(po_record.supplier_name)
            # Check normalized equality or substring inclusion
            is_supplier_match = (
                norm_note_sup == norm_po_sup
                or norm_note_sup in norm_po_sup
                or norm_po_sup in norm_note_sup
            )
            if is_supplier_match:
                passed.append("SUPPLIER_MATCH")
            else:
                failed.append("SUPPLIER_MATCH")
                details["supplier_mismatch"] = {
                    "note_supplier": note.supplier_name,
                    "po_supplier": po_record.supplier_name,
                    "norm_note": norm_note_sup,
                    "norm_po": norm_po_sup,
                }

            # 5. DATE_IN_WINDOW (Delivery date within +-30 days of PO date)
            try:
                d_note = datetime.date.fromisoformat(note.delivery_date)
                d_po = datetime.date.fromisoformat(po_record.order_date)
                delta_days = abs((d_note - d_po).days)
                if delta_days <= self.date_window_days:
                    passed.append("DATE_IN_WINDOW")
                else:
                    failed.append("DATE_IN_WINDOW")
                    details["date_window_exceeded"] = {
                        "note_date": str(d_note),
                        "po_date": str(d_po),
                        "delta_days": delta_days,
                        "limit_days": self.date_window_days,
                    }
            except Exception as e:
                failed.append("DATE_IN_WINDOW")
                details["invalid_date_format"] = str(e)

            # 6. PARTS_EXIST
            allowed_parts = po_record.allowed_parts | self.parts_catalog
            unknown_parts = [
                item.part_no for item in note.line_items if item.part_no not in allowed_parts
            ]
            if not unknown_parts and note.line_items:
                passed.append("PARTS_EXIST")
            else:
                failed.append("PARTS_EXIST")
                details["unknown_parts"] = unknown_parts

        else:
            failed.append("PO_EXISTS")
            failed.append("SUPPLIER_MATCH")
            failed.append("DATE_IN_WINDOW")
            failed.append("PARTS_EXIST")
            details["unknown_po"] = note.po_number

        is_valid = len(failed) == 0
        return ValidationResult(
            is_valid=is_valid,
            passed_rules=passed,
            failed_rules=failed,
            details=details,
        )
