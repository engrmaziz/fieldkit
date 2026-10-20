"""Unit tests for synthetic delivery note generation and degradation pipeline."""

from __future__ import annotations

import json

import numpy as np

from scripts.gen_pdfs import (
    TEMPLATES,
    DeliveryNoteGenerator,
    apply_degradation_pipeline,
    generate_delivery_note_record,
)


def test_generate_single_note_schema() -> None:
    """Verify that generated delivery note records satisfy all required fields."""
    record = generate_delivery_note_record(seed=42, template_id=1, lang="de")
    gt = record.ground_truth

    assert gt.supplier_name.strip() != ""
    assert gt.supplier_address.strip() != ""
    assert gt.delivery_note_no.startswith("LS-")
    assert gt.po_number.startswith("PO-")
    assert len(gt.delivery_date) == 10  # YYYY-MM-DD
    assert len(gt.line_items) >= 1
    for item in gt.line_items:
        assert item.part_no.startswith("PART-")
        assert len(item.description) > 3
        assert item.qty > 0
        assert item.unit in ["STK", "PCS", "MTR", "KG"]

    # Invariant: line items sum to total_qty
    assert sum(item.qty for item in gt.line_items) == gt.total_qty


def test_six_templates_and_bilingual_labels() -> None:
    """Verify all 6 templates support both German (de) and English (en)."""
    assert len(TEMPLATES) == 6
    for t_id in range(1, 7):
        rec_de = generate_delivery_note_record(seed=100 + t_id, template_id=t_id, lang="de")
        rec_en = generate_delivery_note_record(seed=200 + t_id, template_id=t_id, lang="en")
        assert rec_de.template_id == t_id
        assert rec_de.lang == "de"
        assert rec_en.template_id == t_id
        assert rec_en.lang == "en"
        assert rec_de.ground_truth.delivery_note_no.startswith("LS-")
        assert rec_en.ground_truth.delivery_note_no.startswith("DN-")


def test_held_out_templates_partitioning() -> None:
    """Verify templates 5 and 6 are strictly held out for unseen evaluation."""
    generator = DeliveryNoteGenerator(seed=12345)
    dataset = generator.generate_dataset(count=60, split_ratio={"train": 0.6, "val": 0.2, "test": 0.2})

    train_templates = {item["template_id"] for item in dataset["train"]}
    val_templates = {item["template_id"] for item in dataset["val"]}
    unseen_test_templates = {item["template_id"] for item in dataset["unseen_test"]}

    # Templates 5 and 6 must NEVER appear in train or val
    assert 5 not in train_templates
    assert 6 not in train_templates
    assert 5 not in val_templates
    assert 6 not in val_templates

    # Unseen test must ONLY contain templates 5 and 6
    assert unseen_test_templates.issubset({5, 6})


def test_donut_gt_parse_formatting() -> None:
    """Verify that metadata strings match Donut gt_parse format exactly."""
    rec = generate_delivery_note_record(seed=777, template_id=3, lang="de")
    donut_meta = rec.to_donut_dict("test_001.png")

    assert donut_meta["file_name"] == "test_001.png"
    assert "ground_truth" in donut_meta
    parsed = json.loads(donut_meta["ground_truth"])
    assert "gt_parse" in parsed
    gt_parse = parsed["gt_parse"]
    assert gt_parse["supplier_name"] == rec.ground_truth.supplier_name
    assert gt_parse["delivery_note_no"] == rec.ground_truth.delivery_note_no
    assert gt_parse["po_number"] == rec.ground_truth.po_number
    assert gt_parse["total_qty"] == rec.ground_truth.total_qty
    assert len(gt_parse["line_items"]) == len(rec.ground_truth.line_items)


def test_degradation_pipeline_transformation() -> None:
    """Verify that degradation pipeline applies rotation, blur, and artifacts cleanly."""
    # Create clean synthetic RGB image
    clean_img = np.ones((1280, 960, 3), dtype=np.uint8) * 255
    # Draw simple shapes to simulate text
    clean_img[200:220, 100:400] = 0
    clean_img[300:320, 100:500] = 0

    degraded_img, effects = apply_degradation_pipeline(clean_img, seed=42)

    assert degraded_img.shape == clean_img.shape
    assert degraded_img.dtype == np.uint8
    # Should not be identical to clean image
    assert not np.array_equal(clean_img, degraded_img)
    # Check that rotation angle was within [-4.0, 4.0] degrees
    assert "rotation_deg" in effects
    assert -4.5 <= effects["rotation_deg"] <= 4.5
    assert "jpeg_quality" in effects
