"""Test suite verifying Project 4 50+ Document Master Benchmark metrics and regression gates."""

from __future__ import annotations

import pytest

from evals.p4.eval_suite import (
    evaluate_contract_clause_subsystem,
    evaluate_delivery_note_subsystem,
    evaluate_ingestion_subsystem,
    evaluate_playbook_and_diff_subsystem,
)


@pytest.mark.asyncio
async def test_ingestion_subsystem_metrics() -> None:
    res = await evaluate_ingestion_subsystem()
    assert res.files_tested >= 10
    assert res.magic_byte_accuracy_pct == 100.0
    assert res.avg_deskew_residual_deg < 0.5
    assert res.idempotency_rate_pct == 100.0
    assert res.gate_passed is True


def test_delivery_note_subsystem_metrics() -> None:
    # Test on smaller sample slice for ultra-fast unit test execution
    res = evaluate_delivery_note_subsystem(sample_count=10, seed=42)
    assert res.documents_tested >= 10
    assert res.overall_field_f1 >= 0.90
    assert res.po_number_f1 >= 0.95
    assert res.quantity_invariant_pct == 100.0
    assert res.auto_accept_rate_pct >= 75.0
    assert res.p95_latency_ms < 2500.0
    assert res.gate_passed is True


def test_contract_clause_subsystem_metrics() -> None:
    res, clauses = evaluate_contract_clause_subsystem(count=6)
    assert res.documents_tested >= 6
    assert res.span_grounding_accuracy_pct >= 95.0
    assert res.cuad_macro_f1 >= 0.85
    assert res.liability_cap_f1 >= 0.85
    assert res.governing_law_f1 >= 0.90
    assert res.p95_latency_ms < 2500.0
    assert res.gate_passed is True
    assert len(clauses) > 0


def test_playbook_and_diff_subsystem_metrics() -> None:
    _, clauses = evaluate_contract_clause_subsystem(count=6)
    res = evaluate_playbook_and_diff_subsystem(clauses)
    assert res.scenarios_tested > 0
    assert res.playbook_risk_recall_pct >= 90.0
    assert res.hungarian_alignment_accuracy_pct >= 95.0
    assert res.p95_diff_latency_ms < 500.0
    assert res.gate_passed is True
