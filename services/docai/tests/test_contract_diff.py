"""Test suite for clause-level contract version diff and Hungarian alignment."""

from __future__ import annotations

import pytest
from fieldkit_docai.contracts.diff import (
    ContractDiffResult,
    DiffStatus,
    HungarianClauseAligner,
    diff_contracts,
)
from fieldkit_docai.contracts.models import ContractClause, CUADCategory


@pytest.fixture
def v1_clauses() -> list[ContractClause]:
    return [
        ContractClause(
            clause_id="v1_c1",
            section_number="1.1",
            title="Scope",
            text="Vendor shall supply industrial hydraulic valves as specified in Schedule A.",
            char_start=0,
            char_end=74,
            categories=[],
        ),
        ContractClause(
            clause_id="v1_c2",
            section_number="2.1",
            title="Liability",
            text="The aggregate liability of either party shall not exceed EUR 1,000,000.",
            char_start=75,
            char_end=145,
            categories=[CUADCategory.CAP_ON_LIABILITY.value, CUADCategory.LIMITATION_OF_LIABILITY.value],
        ),
        ContractClause(
            clause_id="v1_c3",
            section_number="3.1",
            title="Termination",
            text="Either party may terminate this agreement with 90 days prior written notice.",
            char_start=146,
            char_end=222,
            categories=[CUADCategory.NOTICE_PERIOD_TERMINATION.value, CUADCategory.TERMINATION_FOR_CONVENIENCE.value],
        ),
        ContractClause(
            clause_id="v1_c4",
            section_number="4.1",
            title="Audit",
            text="Halden Industrie shall have the right to audit Supplier's manufacturing facilities.",
            char_start=223,
            char_end=306,
            categories=[CUADCategory.AUDIT_RIGHTS.value],
        ),
    ]


@pytest.fixture
def v2_clauses_modified() -> list[ContractClause]:
    return [
        # c1 is unchanged
        ContractClause(
            clause_id="v2_c1",
            section_number="1.1",
            title="Scope",
            text="Vendor shall supply industrial hydraulic valves as specified in Schedule A.",
            char_start=0,
            char_end=74,
            categories=[],
        ),
        # c2 modified: liability cap reduced to 250,000 EUR
        ContractClause(
            clause_id="v2_c2",
            section_number="2.1",
            title="Liability",
            text="The aggregate liability of Vendor shall not exceed EUR 250,000.",
            char_start=75,
            char_end=138,
            categories=[CUADCategory.CAP_ON_LIABILITY.value, CUADCategory.LIMITATION_OF_LIABILITY.value],
        ),
        # c3 modified: notice period reduced from 90 to 30 days (auto-renewal trap!)
        ContractClause(
            clause_id="v2_c3",
            section_number="3.1",
            title="Termination",
            text="Either party may terminate this agreement with 30 days prior written notice.",
            char_start=139,
            char_end=215,
            categories=[CUADCategory.NOTICE_PERIOD_TERMINATION.value, CUADCategory.TERMINATION_FOR_CONVENIENCE.value],
        ),
        # c4 deleted in v2
        # new clause c5 added: Non-compete
        ContractClause(
            clause_id="v2_c5",
            section_number="5.1",
            title="Non-Compete",
            text="Halden Industrie shall not purchase comparable parts from third-party manufacturers.",
            char_start=216,
            char_end=302,
            categories=[CUADCategory.NON_COMPETE.value],
        ),
    ]


def test_hungarian_aligner_identifies_all_statuses(
    v1_clauses: list[ContractClause], v2_clauses_modified: list[ContractClause]
) -> None:
    diff_res: ContractDiffResult = diff_contracts(v1_clauses, v2_clauses_modified)

    assert diff_res.unchanged_count == 1  # Scope
    assert diff_res.modified_count == 2   # Liability & Termination
    assert diff_res.deleted_count == 1    # Audit was removed
    assert diff_res.added_count == 1      # Non-compete was added


def test_material_redline_detection(
    v1_clauses: list[ContractClause], v2_clauses_modified: list[ContractClause]
) -> None:
    diff_res: ContractDiffResult = diff_contracts(v1_clauses, v2_clauses_modified)

    # 2 modified clauses should both be flagged as material changes
    assert diff_res.material_change_count >= 2

    # Verify notice period reduction flag
    term_diff = next(
        item for item in diff_res.items
        if item.clause_v1_id == "v1_c3" and item.status == DiffStatus.MODIFIED
    )
    assert term_diff.is_material is True
    assert any("30" in r or "notice" in r.lower() or "number" in r.lower() for r in term_diff.material_reasons)
    assert "90" in term_diff.text_diff
    assert "30" in term_diff.text_diff


def test_reordered_clauses_alignment(v1_clauses: list[ContractClause]) -> None:
    # Reverse order in v2
    v2_reversed = [
        ContractClause(
            clause_id=f"rev_{c.clause_id}",
            section_number=c.section_number,
            title=c.title,
            text=c.text,
            char_start=0,
            char_end=len(c.text),
            categories=c.categories,
        )
        for c in reversed(v1_clauses)
    ]

    aligner = HungarianClauseAligner()
    pairs = aligner.align(v1_clauses, v2_reversed)

    # Every clause should match its corresponding reversed counterpart with UNCHANGED status
    for v1_idx, v2_idx, score in pairs:
        assert v1_idx is not None and v2_idx is not None
        c1 = v1_clauses[v1_idx]
        c2 = v2_reversed[v2_idx]
        assert c1.section_number == c2.section_number
        assert score >= 0.95


def test_empty_contract_diff() -> None:
    diff_res = diff_contracts([], [])
    assert len(diff_res.items) == 0
    assert diff_res.material_change_count == 0
