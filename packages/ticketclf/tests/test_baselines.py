"""Unit and integration tests for ticket classification baselines."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fieldkit_ticketclf.baselines import (
    DenseEmbeddingBaseline,
    LLMFewShotBaseline,
    LLMZeroShotBaseline,
    TfidfBaseline,
    TicketClassificationOutput,
)
from fieldkit_ticketclf.data import ALLOWED_PRIORITIES, ALLOWED_QUEUES, generate_ticket_corpus


@pytest.fixture
def sample_corpus() -> list[dict[str, Any]]:
    return generate_ticket_corpus(n_tickets=60, seed=42)


def test_ticket_classification_output_validation() -> None:
    # Valid output
    out = TicketClassificationOutput(queue="technical_defect", priority="critical", confidence=0.95)
    assert out.queue == "technical_defect"
    assert out.priority == "critical"
    assert out.confidence == 0.95

    # Case normalization and string confidence parsing
    out2 = TicketClassificationOutput.model_validate(
        {"queue": "  ORDER_DELIVERY  ", "priority": " HIGH ", "confidence": "0.8"}
    )
    assert out2.queue == "order_delivery"
    assert out2.priority == "high"
    assert out2.confidence == 0.8

    # Fallback on invalid queue and priority
    out3 = TicketClassificationOutput(queue="unknown_queue", priority="extreme", confidence=1.5)
    assert out3.queue == "other"
    assert out3.priority == "medium"
    assert out3.confidence == 1.0  # clamped to max 1.0


def test_tfidf_baseline_fit_and_predict(sample_corpus: list[dict[str, Any]]) -> None:
    clf = TfidfBaseline(seed=42)

    # Must raise before fit
    with pytest.raises(RuntimeError):
        clf.predict_one("Pump is leaking oil")

    clf.fit(sample_corpus)

    # Single prediction
    pred = clf.predict_one("Severe oil leakage on hydraulic cylinder HX-400 at DE-HAM", language="en")
    assert pred.queue in ALLOWED_QUEUES
    assert pred.priority in ALLOWED_PRIORITIES
    assert 0.0 <= pred.confidence <= 1.0

    # German ticket prediction
    pred_de = clf.predict_one("Dringende Reklamation wegen Ölleckage am Wegeventil", language="de")
    assert pred_de.queue in ALLOWED_QUEUES
    assert pred_de.priority in ALLOWED_PRIORITIES

    # Batch prediction
    batch_preds = clf.predict_batch(sample_corpus[:5])
    assert len(batch_preds) == 5
    for bp in batch_preds:
        assert bp.queue in ALLOWED_QUEUES
        assert bp.priority in ALLOWED_PRIORITIES


@pytest.mark.asyncio
async def test_dense_embedding_baseline(sample_corpus: list[dict[str, Any]]) -> None:
    clf = DenseEmbeddingBaseline(seed=42)
    await clf.fit_async(sample_corpus[:30])

    pred = await clf.predict_async("Consignment tracking missing for PO-12345", language="en")
    assert pred.queue in ALLOWED_QUEUES
    assert pred.priority in ALLOWED_PRIORITIES
    assert 0.0 <= pred.confidence <= 1.0


@pytest.mark.asyncio
async def test_llm_zeroshot_baseline() -> None:
    mock_client = MagicMock()
    mock_client.structured_output_from_template = AsyncMock(
        return_value=TicketClassificationOutput(
            queue="billing_inquiry",
            priority="high",
            confidence=0.92,
        )
    )

    clf = LLMZeroShotBaseline(client=mock_client)
    res = await clf.predict_async("Disputed invoice with wrong VAT calculation", language="en")

    assert res.queue == "billing_inquiry"
    assert res.priority == "high"
    assert res.confidence == 0.92
    assert mock_client.structured_output_from_template.called


@pytest.mark.asyncio
async def test_llm_fewshot_baseline(sample_corpus: list[dict[str, Any]]) -> None:
    mock_client = MagicMock()
    mock_client.structured_output_from_template = AsyncMock(
        return_value=TicketClassificationOutput(
            queue="returns_rma",
            priority="medium",
            confidence=0.88,
        )
    )

    clf = LLMFewShotBaseline(client=mock_client, n_neighbors=3)
    clf.fit(sample_corpus)

    # Test nearest-neighbor exemplar retrieval
    exemplars = clf._get_exemplars("Defective part returned for warranty inspection")
    assert len(exemplars) == 3
    for ex in exemplars:
        assert "text" in ex
        assert "queue" in ex
        assert "priority" in ex

    res = await clf.predict_async("Defective part returned for warranty inspection", language="en")
    assert res.queue == "returns_rma"
    assert res.priority == "medium"
    assert res.confidence == 0.88
    assert mock_client.structured_output_from_template.called
