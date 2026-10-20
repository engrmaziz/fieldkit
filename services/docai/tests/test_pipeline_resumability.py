"""Test suite for pipeline idempotency and resumability after interrupted/killed workers."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fieldkit_docai.models import DocumentStatus, StepStatus
from fieldkit_docai.storage import DocumentStore
from fieldkit_docai.worker import DocumentWorker
from PIL import Image


def create_sample_png() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (300, 200), color="white")
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_worker_step_recording_and_idempotence(tmp_path: Path) -> None:
    db_path = tmp_path / "test_docai.db"
    store = DocumentStore(db_url=f"sqlite:///{db_path}")
    worker = DocumentWorker(store=store)

    doc_bytes = create_sample_png()
    doc = await store.create_document(
        filename="test_delivery.png",
        content=doc_bytes,
        mime_type="image/png",
    )
    doc_id = doc.document_id

    # 1. Run pipeline to completion
    result = await worker.process_document(doc_id)
    assert result.status == DocumentStatus.COMPLETED

    steps = await store.get_document_steps(doc_id)
    step_names = [s.step_name for s in steps]
    assert "UPLOAD" in step_names
    assert "PREPROCESS" in step_names
    assert "OCR" in step_names
    assert "LAYOUT" in step_names
    assert "CLASSIFY" in step_names
    assert all(s.status == StepStatus.COMPLETED for s in steps)

    # 2. Re-running the worker on completed document should be idempotent
    re_result = await worker.process_document(doc_id)
    assert re_result.status == DocumentStatus.COMPLETED
    # Steps should not duplicate
    re_steps = await store.get_document_steps(doc_id)
    assert len(re_steps) == len(steps)


@pytest.mark.asyncio
async def test_worker_resumability_after_interruption(tmp_path: Path) -> None:
    db_path = tmp_path / "test_resumability.db"
    store = DocumentStore(db_url=f"sqlite:///{db_path}")

    doc_bytes = create_sample_png()
    doc = await store.create_document(
        filename="interrupted_contract.png",
        content=doc_bytes,
        mime_type="image/png",
    )
    doc_id = doc.document_id

    # Simulate that UPLOAD and PREPROCESS finished before process was killed
    await store.record_step(
        doc_id=doc_id, step_name="UPLOAD", status=StepStatus.COMPLETED, duration_ms=12.0
    )
    await store.record_step(
        doc_id=doc_id, step_name="PREPROCESS", status=StepStatus.COMPLETED, duration_ms=45.0
    )
    await store.record_step(
        doc_id=doc_id,
        step_name="OCR",
        status=StepStatus.FAILED,
        duration_ms=10.0,
        error="Worker killed (SIGKILL)",
    )

    # Resume processing with new worker instance
    worker = DocumentWorker(store=store)
    resumed_doc = await worker.process_document(doc_id)

    assert resumed_doc.status == DocumentStatus.COMPLETED

    # Check that OCR was retried and completed
    steps = await store.get_document_steps(doc_id)
    ocr_steps = [s for s in steps if s.step_name == "OCR"]
    assert any(s.status == StepStatus.COMPLETED for s in ocr_steps)
