"""Unit tests for Donut field extractor, inference pipeline, and confidence scoring."""

from __future__ import annotations

import numpy as np
from fieldkit_docai.delivery.donut_infer import (
    DonutExtractionResult,
    DonutFieldExtractor,
    parse_donut_xml_to_dict,
)


def test_donut_extractor_init() -> None:
    """Verify initialization of Donut field extractor with CPU execution."""
    extractor = DonutFieldExtractor(device="cpu")
    assert extractor.device == "cpu"
    assert extractor.is_ready()


def test_parse_donut_xml_to_dict() -> None:
    """Verify parsing of Donut structured XML sequence into nested dictionary."""
    xml_str = (
        "<s_delivery_note>"
        "<s_supplier_name>Halden Hydraulik GmbH</s_supplier_name>"
        "<s_supplier_address>Industriestrasse 10, 70565 Stuttgart</s_supplier_address>"
        "<s_delivery_note_no>LS-2026-9901</s_delivery_note_no>"
        "<s_po_number>PO-2026-4412</s_po_number>"
        "<s_delivery_date>2026-05-18</s_delivery_date>"
        "<s_line_items>"
        "<s_item><s_part_no>PART-102</s_part_no><s_description>Ventil 24V</s_description><s_qty>15</s_qty><s_unit>STK</s_unit></s_item>"
        "<s_item><s_part_no>PART-105</s_part_no><s_description>Dichtring 50mm</s_description><s_qty>30</s_qty><s_unit>STK</s_unit></s_item>"
        "</s_line_items>"
        "<s_total_qty>45</s_total_qty>"
        "</s_delivery_note>"
    )

    parsed = parse_donut_xml_to_dict(xml_str)

    assert parsed["supplier_name"] == "Halden Hydraulik GmbH"
    assert parsed["supplier_address"] == "Industriestrasse 10, 70565 Stuttgart"
    assert parsed["delivery_note_no"] == "LS-2026-9901"
    assert parsed["po_number"] == "PO-2026-4412"
    assert parsed["delivery_date"] == "2026-05-18"
    assert len(parsed["line_items"]) == 2
    assert parsed["line_items"][0]["part_no"] == "PART-102"
    assert parsed["line_items"][0]["qty"] == 15
    assert parsed["line_items"][1]["qty"] == 30
    assert parsed["total_qty"] == 45


def test_donut_extractor_predict_synthetic() -> None:
    """Verify extraction and confidence computation on a delivery note page."""
    extractor = DonutFieldExtractor(device="cpu")

    # Synthetic document image
    img = np.ones((1280, 960, 3), dtype=np.uint8) * 255

    # Provide known ground truth or mock overlay
    sample_text = (
        "Lieferschein LS-2026-1102\n"
        "Lieferant: Halden Armaturen GmbH\n"
        "Industrieweg 5, 20457 Hamburg\n"
        "Bestellnummer: PO-2026-0819\n"
        "Datum: 2026-06-12\n"
        "PART-0044 Kugelhahn DN50 10 STK\n"
        "Gesamtmenge: 10 STK"
    )

    result = extractor.predict_image(img, ocr_text_hint=sample_text)

    assert isinstance(result, DonutExtractionResult)
    assert 0.0 <= result.confidence <= 1.0
    assert result.fields.delivery_note_no == "LS-2026-1102"
    assert result.fields.po_number == "PO-2026-0819"
    assert result.fields.supplier_name == "Halden Armaturen GmbH"
    assert result.fields.total_qty == 10
    assert len(result.fields.line_items) == 1
    assert result.fields.line_items[0].part_no == "PART-0044"
    assert result.fields.line_items[0].qty == 10


def test_donut_extractor_batch_predict() -> None:
    """Verify batch inference handles multiple pages and maintains consistent output."""
    extractor = DonutFieldExtractor(device="cpu")

    img1 = np.ones((640, 480, 3), dtype=np.uint8) * 255
    img2 = np.ones((640, 480, 3), dtype=np.uint8) * 255

    hints = [
        "LS-2026-0001 PO-2026-0001 Lieferant: Alpha GmbH Gesamt: 5",
        "LS-2026-0002 PO-2026-0002 Lieferant: Beta GmbH Gesamt: 12",
    ]

    results = extractor.predict_batch([img1, img2], ocr_hints=hints, batch_size=2)

    assert len(results) == 2
    assert results[0].fields.delivery_note_no == "LS-2026-0001"
    assert results[1].fields.delivery_note_no == "LS-2026-0002"
    assert results[0].fields.supplier_name == "Alpha GmbH"
    assert results[1].fields.supplier_name == "Beta GmbH"
    assert results[0].confidence > 0.0
    assert results[1].confidence > 0.0
