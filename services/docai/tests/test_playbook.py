"""Test suite for deterministic legal playbook rules engine."""

from __future__ import annotations

import pytest
from fieldkit_docai.contracts.models import ContractClause, CUADCategory
from fieldkit_docai.contracts.playbook import FindingSeverity, FindingStatus, PlaybookEvaluator


@pytest.fixture
def evaluator() -> PlaybookEvaluator:
    return PlaybookEvaluator.from_yaml("playbooks/halden_v1.yaml")


def test_evaluator_compliant_clauses(evaluator: PlaybookEvaluator) -> None:
    clauses = [
        ContractClause(
            clause_id="c_cap",
            section_number="2.1",
            text="In no event shall aggregate liability exceed 2x the annual contract fees.",
            char_start=0,
            char_end=72,
            categories=[CUADCategory.CAP_ON_LIABILITY.value],
        ),
        ContractClause(
            clause_id="c_law",
            section_number="3.1",
            text="This Agreement is governed by the laws of Germany. The UN Convention (CISG) is excluded.",
            char_start=73,
            char_end=162,
            categories=[CUADCategory.GOVERNING_LAW.value],
        ),
        ContractClause(
            clause_id="c_notice",
            section_number="4.1",
            text="Either party may terminate without cause upon 90 days prior written notice.",
            char_start=163,
            char_end=238,
            categories=[CUADCategory.NOTICE_PERIOD_TERMINATION.value],
        ),
        ContractClause(
            clause_id="c_indemnity",
            section_number="5.1",
            text="Supplier shall defend and indemnify Halden Industrie against third-party IP infringement claims.",
            char_start=239,
            char_end=335,
            categories=[CUADCategory.INDEMNIFICATION.value],
        ),
        ContractClause(
            clause_id="c_warranty",
            section_number="6.1",
            text="Supplier warrants all parts against defects for a period of 24 months.",
            char_start=336,
            char_end=406,
            categories=[CUADCategory.WARRANTY.value],
        ),
    ]

    report = evaluator.evaluate(clauses)
    assert report.is_compliant is True
    assert len(report.findings) >= 5
    # All checked rules should pass
    failed_findings = [f for f in report.findings if f.status == FindingStatus.FAIL]
    assert len(failed_findings) == 0


def test_evaluator_flags_excessive_liability_cap(evaluator: PlaybookEvaluator) -> None:
    clause = ContractClause(
        clause_id="c_bad_cap",
        section_number="2.1",
        text="Supplier's maximum liability is capped at 5x the annual contract value.",
        char_start=0,
        char_end=71,
        categories=[CUADCategory.CAP_ON_LIABILITY.value],
    )

    report = evaluator.evaluate([clause])
    assert report.is_compliant is False

    cap_finding = next((f for f in report.findings if f.rule_id == "RULE_LIABILITY_CAP"), None)
    assert cap_finding is not None
    assert cap_finding.status == FindingStatus.FAIL
    assert cap_finding.severity == FindingSeverity.CRITICAL
    assert "exceeds" in cap_finding.message.lower()
    assert cap_finding.fallback_recommendation != ""


def test_evaluator_flags_foreign_governing_law(evaluator: PlaybookEvaluator) -> None:
    clause = ContractClause(
        clause_id="c_us_law",
        section_number="3.1",
        text="This Agreement shall be governed by the laws of the State of New York, USA.",
        char_start=0,
        char_end=76,
        categories=[CUADCategory.GOVERNING_LAW.value],
    )

    report = evaluator.evaluate([clause])
    assert report.is_compliant is False

    law_finding = next((f for f in report.findings if f.rule_id == "RULE_GOVERNING_LAW"), None)
    assert law_finding is not None
    assert law_finding.status == FindingStatus.FAIL
    assert law_finding.severity == FindingSeverity.HIGH
    assert "new york" in law_finding.message.lower() or "jurisdiction" in law_finding.message.lower()


def test_evaluator_flags_short_notice_period(evaluator: PlaybookEvaluator) -> None:
    clause = ContractClause(
        clause_id="c_short_notice",
        section_number="4.1",
        text="The agreement may be terminated with 30 days notice prior to the renewal date.",
        char_start=0,
        char_end=79,
        categories=[CUADCategory.NOTICE_PERIOD_TERMINATION.value],
    )

    report = evaluator.evaluate([clause])
    notice_finding = next((f for f in report.findings if f.rule_id == "RULE_RENEWAL_NOTICE"), None)
    assert notice_finding is not None
    assert notice_finding.status == FindingStatus.FAIL
    assert notice_finding.severity == FindingSeverity.HIGH
    assert "30" in notice_finding.message
    assert "90" in notice_finding.message


def test_evaluator_german_contracts(evaluator: PlaybookEvaluator) -> None:
    clause_de_law = ContractClause(
        clause_id="c_de_law",
        section_number="§ 8",
        text="Es gilt das Recht der Bundesrepublik Deutschland. Das UN-Kaufrecht (CISG) ist ausgeschlossen.",
        char_start=0,
        char_end=94,
        categories=[CUADCategory.GOVERNING_LAW.value],
    )
    clause_de_notice = ContractClause(
        clause_id="c_de_notice",
        section_number="§ 9",
        text="Die Kündigungsfrist beträgt 30 Tage zum Monatsende.",
        char_start=95,
        char_end=146,
        categories=[CUADCategory.NOTICE_PERIOD_TERMINATION.value],
    )

    report = evaluator.evaluate([clause_de_law, clause_de_notice])

    law_f = next(f for f in report.findings if f.rule_id == "RULE_GOVERNING_LAW")
    assert law_f.status == FindingStatus.PASS

    notice_f = next(f for f in report.findings if f.rule_id == "RULE_RENEWAL_NOTICE")
    assert notice_f.status == FindingStatus.FAIL
    assert "30" in notice_f.message
