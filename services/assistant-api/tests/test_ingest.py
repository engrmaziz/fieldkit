"""Integration tests for Assistant API health and corpus ingestion endpoints."""

import pytest
from fastapi.testclient import TestClient
from fieldkit_assistant.main import app
from fieldkit_assistant.routers.ingest import CHUNK_CACHE, DOC_CACHE
from fieldkit_common.auth import Principal, get_current_principal


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    DOC_CACHE.clear()
    CHUNK_CACHE.clear()


@pytest.fixture
def admin_principal() -> Principal:
    return Principal(
        sub="jana-admin",
        username="jana",
        roles=["admin"],
        plant=None,
    )


@pytest.fixture
def viewer_principal() -> Principal:
    return Principal(
        sub="viewer-001",
        username="viewer",
        roles=["support"],
        plant="DE-STR",
    )


def test_healthz_and_readyz() -> None:
    client = TestClient(app)
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json() == {"status": "healthy", "service": "assistant-api"}

    resp_ready = client.get("/readyz")
    assert resp_ready.status_code == 200
    assert resp_ready.json() == {"status": "ready", "service": "assistant-api"}


def test_ingest_requires_admin_role(viewer_principal: Principal) -> None:
    app.dependency_overrides[get_current_principal] = lambda: viewer_principal
    client = TestClient(app)

    resp = client.post("/api/assistant/ingest")
    assert resp.status_code == 403
    assert "Required role in ['admin']" in resp.json()["detail"]
    app.dependency_overrides.clear()


def test_ingest_corpus_success_and_idempotency(admin_principal: Principal) -> None:
    app.dependency_overrides[get_current_principal] = lambda: admin_principal
    client = TestClient(app)

    # First run: processes all documents
    resp = client.post("/api/assistant/ingest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_documents"] >= 40
    assert data["processed_documents"] >= 40
    assert data["skipped_documents"] == 0
    assert data["total_chunks"] >= 40
    assert data["total_tokens"] > 1000

    # Second run without force_rechunk: 100% idempotent skipped
    resp_idempotent = client.post("/api/assistant/ingest")
    assert resp_idempotent.status_code == 200
    data_2 = resp_idempotent.json()
    assert data_2["processed_documents"] == 0
    assert data_2["skipped_documents"] == data["total_documents"]
    assert data_2["total_chunks"] == data["total_chunks"]

    # Verify chunks inspection endpoint
    resp_chunks = client.get("/api/assistant/chunks")
    assert resp_chunks.status_code == 200
    chunks = resp_chunks.json()
    assert len(chunks) == data["total_chunks"]

    # Verify every chunk has heading path and valid language
    for chunk in chunks:
        assert len(chunk["heading_path"]) >= 1
        assert chunk["language"] in ("de", "en", "pl")
        assert chunk["tsv_config"] in ("german", "english", "simple")
        assert chunk["token_count"] <= 512

    app.dependency_overrides.clear()
