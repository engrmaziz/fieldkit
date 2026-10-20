"""Test suite for CUAD multi-label contract clause classifier."""

from __future__ import annotations

import pytest
from fieldkit_docai.contracts.cuad_classifier import CUADClauseClassifier
from fieldkit_docai.contracts.models import ContractClause, CUADCategory


@pytest.fixture
def classifier() -> CUADClauseClassifier:
    return CUADClauseClassifier()


def test_classify_limitation_of_liability_and_cap(classifier: CUADClauseClassifier) -> None:
    text = (
        "In no event shall Supplier's total aggregate liability arising out of this Agreement "
        "exceed EUR 500,000 or the total fees paid by Halden Industrie in the prior 12 months."
    )
    categories, scores = classifier.predict(text)

    assert CUADCategory.LIMITATION_OF_LIABILITY in categories
    assert CUADCategory.CAP_ON_LIABILITY in categories
    assert scores[CUADCategory.LIMITATION_OF_LIABILITY] >= 0.50
    assert scores[CUADCategory.CAP_ON_LIABILITY] >= 0.50


def test_classify_german_jurisdiction_and_governing_law(classifier: CUADClauseClassifier) -> None:
    text = (
        "Es gilt ausschließlich das Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts (CISG). "
        "Ausschließlicher Gerichtsstand für alle Streitigkeiten ist Hamburg."
    )
    categories, scores = classifier.predict(text)

    assert CUADCategory.GOVERNING_LAW in categories
    assert CUADCategory.JURISDICTION in categories
    assert scores[CUADCategory.GOVERNING_LAW] >= 0.50
    assert scores[CUADCategory.JURISDICTION] >= 0.50


def test_classify_termination_notice_period(classifier: CUADClauseClassifier) -> None:
    text = (
        "Either party may terminate this Agreement without cause upon giving ninety (90) days' "
        "prior written notice to the other party."
    )
    categories, scores = classifier.predict(text)

    assert CUADCategory.TERMINATION_FOR_CONVENIENCE in categories
    assert CUADCategory.NOTICE_PERIOD_TERMINATION in categories


def test_classify_confidentiality(classifier: CUADClauseClassifier) -> None:
    text = (
        "Each party agrees to hold all confidential information and trade secrets in strict confidence "
        "and not disclose such proprietary information to any third party."
    )
    categories, scores = classifier.predict(text)

    assert CUADCategory.CONFIDENTIALITY in categories
    assert scores[CUADCategory.CONFIDENTIALITY] >= 0.60


def test_custom_threshold_filtering(classifier: CUADClauseClassifier) -> None:
    text = "Supplier shall maintain reasonable commercial general liability insurance."
    # With standard threshold
    cats_std, _ = classifier.predict(text, threshold=0.40)
    assert CUADCategory.INSURANCE in cats_std

    # With very strict threshold
    cats_strict, _ = classifier.predict(text, threshold=0.99)
    assert len(cats_strict) == 0


def test_predict_batch_enriches_contract_clauses(classifier: CUADClauseClassifier) -> None:
    clauses = [
        ContractClause(
            clause_id="c1",
            text="The liability of Vendor shall be capped at 100,000 EUR.",
            char_start=0,
            char_end=56,
        ),
        ContractClause(
            clause_id="c2",
            text="This agreement is governed by the laws of Germany.",
            char_start=57,
            char_end=107,
        ),
    ]

    classifier.predict_batch(clauses)

    assert CUADCategory.LIMITATION_OF_LIABILITY in clauses[0].categories
    assert CUADCategory.GOVERNING_LAW in clauses[1].categories
    assert len(clauses[0].category_scores) > 0
    assert len(clauses[1].category_scores) > 0


def test_unrelated_text_produces_no_false_positive(classifier: CUADClauseClassifier) -> None:
    text = "The cafeteria in plant Hamburg serves lunch from 12:00 to 13:30 on weekdays."
    categories, scores = classifier.predict(text)
    assert categories == []
