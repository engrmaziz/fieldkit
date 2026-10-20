"""Delivery note processing, Donut field extraction, validators, and VLM fallback."""

from fieldkit_docai.delivery.decision import (
    DeliveryDecision,
    DeliveryDecisionEngine,
    tune_threshold_tau,
)
from fieldkit_docai.delivery.donut_infer import (
    DeliveryNoteFields,
    DonutExtractionResult,
    DonutFieldExtractor,
    LineItemField,
    dict_to_donut_xml,
    parse_donut_xml_to_dict,
)
from fieldkit_docai.delivery.validators import (
    DeliveryNoteValidator,
    MockPurchaseOrderRegistry,
    PurchaseOrderRecord,
    ValidationResult,
)
from fieldkit_docai.delivery.vlm_fallback import (
    MockVLMFallbackClient,
    VLMFallbackClient,
)

__all__ = [
    "DeliveryDecision",
    "DeliveryDecisionEngine",
    "DeliveryNoteFields",
    "DeliveryNoteValidator",
    "DonutExtractionResult",
    "DonutFieldExtractor",
    "LineItemField",
    "MockPurchaseOrderRegistry",
    "MockVLMFallbackClient",
    "PurchaseOrderRecord",
    "ValidationResult",
    "VLMFallbackClient",
    "dict_to_donut_xml",
    "parse_donut_xml_to_dict",
    "tune_threshold_tau",
]
