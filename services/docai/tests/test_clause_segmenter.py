"""Test suite for hierarchical contract clause segmenter and span grounding."""

from __future__ import annotations

import pytest
from fieldkit_docai.contracts.segmenter import HierarchicalClauseSegmenter
from fieldkit_docai.models import LayoutBlock, PageResult


@pytest.fixture
def sample_english_contract() -> str:
    return (
        "MASTER SERVICES AGREEMENT\n\n"
        "1. DEFINITIONS AND INTERPRETATION\n"
        "1.1 \"Agreement\" means this Master Services Agreement including all schedules.\n"
        "1.2 \"Confidential Information\" means all non-public proprietary data.\n\n"
        "2. LIMITATION OF LIABILITY\n"
        "2.1 In no event shall either party's aggregate liability exceed EUR 500,000.\n"
        "2.2 Neither party shall be liable for indirect or consequential damages.\n\n"
        "3. GOVERNING LAW AND JURISDICTION\n"
        "3.1 This Agreement shall be governed by the laws of the Federal Republic of Germany.\n"
        "3.2 The courts of Hamburg shall have exclusive jurisdiction.\n"
    )


@pytest.fixture
def sample_german_contract() -> str:
    return (
        "LIEFER- UND RAHMENVERTRAG\n\n"
        "§ 1 Vertragsgegenstand und Leistungsumfang\n"
        "1.1 Der Lieferant verpflichtet sich zur Lieferung von Präzisionsbauteilen.\n"
        "1.2 Änderungen des Leistungsumfangs bedürfen der Schriftform.\n\n"
        "§ 2 Haftung und Gewährleistung\n"
        "2.1 Die Haftung des Lieferanten für leichte Fahrlässigkeit wird ausgeschlossen.\n"
        "2.2 Die Gesamthaftung ist auf das Zweifache des jährlichen Auftragswerts begrenzt.\n\n"
        "§ 3 Kündigung\n"
        "3.1 Jede Partei kann den Vertrag mit einer Frist von 90 Tagen zum Quartalsende kündigen.\n"
    )


def test_segment_decimal_numbering(sample_english_contract: str) -> None:
    segmenter = HierarchicalClauseSegmenter()
    clauses = segmenter.segment_text(sample_english_contract)

    assert len(clauses) >= 6
    # Check that parent and child sections are detected
    sec_nums = [c.section_number for c in clauses]
    assert "1" in sec_nums or "1." in sec_nums or any("1" in s for s in sec_nums)
    assert any("2.1" in s for s in sec_nums)

    # Find liability clause
    liability_clauses = [c for c in clauses if "2.1" in c.section_number]
    assert len(liability_clauses) == 1
    assert "500,000" in liability_clauses[0].text


def test_strict_span_grounding_invariant(sample_english_contract: str) -> None:
    """Every extracted clause must strictly match its character offsets in the original text."""
    segmenter = HierarchicalClauseSegmenter()
    clauses = segmenter.segment_text(sample_english_contract)

    assert len(clauses) > 0
    for clause in clauses:
        grounded_span = sample_english_contract[clause.char_start : clause.char_end]
        assert grounded_span == clause.text, (
            f"Grounding failure for clause {clause.clause_id}: "
            f"expected '{clause.text[:30]}...' but found '{grounded_span[:30]}...'"
        )


def test_strict_span_grounding_german(sample_german_contract: str) -> None:
    segmenter = HierarchicalClauseSegmenter()
    clauses = segmenter.segment_text(sample_german_contract)

    assert len(clauses) >= 4
    for clause in clauses:
        grounded_span = sample_german_contract[clause.char_start : clause.char_end]
        assert grounded_span == clause.text
        assert clause.char_end > clause.char_start


def test_hierarchical_parent_child_links(sample_english_contract: str) -> None:
    segmenter = HierarchicalClauseSegmenter()
    clauses = segmenter.segment_text(sample_english_contract)

    # Clause 2.1 should have a parent link pointing to Section 2
    clause_2_1 = next((c for c in clauses if "2.1" in c.section_number), None)
    assert clause_2_1 is not None
    assert clause_2_1.parent_clause_id is not None

    parent = next((c for c in clauses if c.clause_id == clause_2_1.parent_clause_id), None)
    assert parent is not None
    assert "2" in parent.section_number


def test_layout_block_bounding_box_mapping() -> None:
    text_p0 = "1. SCOPE OF SUPPLY\n1.1 Vendor shall supply parts.\n"
    blocks = [
        LayoutBlock(
            block_id="b0",
            page_idx=0,
            block_type="header",
            bbox=[50, 100, 400, 130],
            text="1. SCOPE OF SUPPLY",
        ),
        LayoutBlock(
            block_id="b1",
            page_idx=0,
            block_type="paragraph",
            bbox=[50, 140, 500, 180],
            text="1.1 Vendor shall supply parts.",
        ),
    ]
    page = PageResult(
        page_idx=0,
        width=600,
        height=800,
        text=text_p0,
        layout_blocks=blocks,
    )

    segmenter = HierarchicalClauseSegmenter()
    clauses = segmenter.segment_pages([page])

    assert len(clauses) >= 2
    # Check bounding box aggregation
    c_1_1 = next((c for c in clauses if "1.1" in c.section_number), None)
    assert c_1_1 is not None
    assert c_1_1.bbox != [0, 0, 0, 0]
    assert c_1_1.page_idx == 0


def test_empty_and_unstructured_text() -> None:
    segmenter = HierarchicalClauseSegmenter()
    clauses_empty = segmenter.segment_text("")
    assert clauses_empty == []

    unstructured = "This is a simple unstructured memo without numbered sections."
    clauses_unstructured = segmenter.segment_text(unstructured)
    assert len(clauses_unstructured) == 1
    assert clauses_unstructured[0].text == unstructured
    assert clauses_unstructured[0].char_start == 0
    assert clauses_unstructured[0].char_end == len(unstructured)
