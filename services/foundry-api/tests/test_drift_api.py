"""Tests for Foundry API drift and governance endpoints."""

from __future__ import annotations

import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient
from fieldkit_foundry.main import app
from fieldkit_ingest.drift import (
    DriftEvent,
    DriftEventType,
    DriftSeverity,
    DriftStore,
    RenameSuggestion,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz(client: TestClient) -> None:
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_drift_events_and_approve(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = DriftStore(postgres_dsn="postgresql://invalid:5432/none", fallback_dir=tmp_dir)
        # Patch fallback_path in DriftStore
        monkeypatch.setattr(DriftStore, "__init__", lambda self, *args, **kwargs: None)
        monkeypatch.setattr(DriftStore, "fallback_path", store.fallback_path, raising=False)
        monkeypatch.setattr(DriftStore, "save_events", store.save_events, raising=False)
        monkeypatch.setattr(DriftStore, "approve_mapping", store.approve_mapping, raising=False)
        monkeypatch.setattr(DriftStore, "get_active_overrides", store.get_active_overrides, raising=False)

        event_id = f"drift_{uuid.uuid4().hex[:12]}"
        event = DriftEvent(
            event_id=event_id,
            run_id="run_test_api",
            source="erp_vendors",
            event_type=DriftEventType.COLUMN_REMOVED,
            severity=DriftSeverity.BLOCK,
            column_name="legal_name",
            details={"message": "Missing required contract column"},
            suggestion=RenameSuggestion(
                old_name="legal_name",
                new_name="company_title",
                confidence=0.92,
                reason="High semantic string similarity",
            ),
            status="suggested",
        )
        store.save_events([event])

        # 1. Query events
        resp = client.get("/drift/events?source=erp_vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        found = next((e for e in data if e["event_id"] == event_id), None)
        assert found is not None
        assert found["status"] == "suggested"

        # 2. Approve mapping
        resp_approve = client.post(f"/drift/{event_id}/approve", json={"approved_by": "jana"})
        assert resp_approve.status_code == 200
        assert resp_approve.json()["status"] == "approved"

        # 3. Query overrides
        resp_overrides = client.get("/drift/overrides?source=erp_vendors")
        assert resp_overrides.status_code == 200
        overrides = resp_overrides.json()
        assert overrides.get("erp_vendors:legal_name") == "company_title"
