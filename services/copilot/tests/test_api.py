"""Unit and integration tests for Ops Copilot FastAPI service."""

from fastapi.testclient import TestClient
from fieldkit_copilot.main import app

client = TestClient(app)


def test_healthz_and_readyz() -> None:
    """Verifies service probes."""
    r_h = client.get("/healthz")
    assert r_h.status_code == 200
    assert r_h.json()["status"] == "healthy"

    r_r = client.get("/readyz")
    assert r_r.status_code == 200
    assert r_r.json()["status"] == "ready"


def test_ingest_rma_ticket_pauses_and_approval_executes() -> None:
    """Verifies full lifecycle via REST: ingest -> pauses awaiting approval -> approve -> completed."""
    ticket_id = "TICK-API-101"
    ingest_payload = {
        "ticket_id": ticket_id,
        "raw_text": "Zylinder an PO-1001 leckt stark. Bitte um RMA Rücksendung.",
        "order_id": "PO-1001",
        "internal_only": False,
    }

    # 1. Ingest
    r_ingest = client.post("/copilot/tickets/ingest", json=ingest_payload)
    assert r_ingest.status_code == 200
    data_ingest = r_ingest.json()
    assert data_ingest["ticket_id"] == ticket_id
    assert data_ingest["status"] == "awaiting_approval"
    assert data_ingest["awaiting_approval"] is True
    assert data_ingest["action_plan"] is not None

    # 2. Get State
    r_get = client.get(f"/copilot/tickets/{ticket_id}")
    assert r_get.status_code == 200
    data_get = r_get.json()
    assert data_get["awaiting_approval"] is True

    # 3. Approve
    r_app = client.post(
        f"/copilot/tickets/{ticket_id}/approve",
        json={"decision": "approved", "feedback": "Approved by supervisor Lukas"},
    )
    assert r_app.status_code == 200
    data_app = r_app.json()
    assert data_app["status"] == "completed"
    assert data_app["awaiting_approval"] is False
    assert len(data_app["tool_results"]) > 0

    # 4. Fetch Audit Trail
    r_audit = client.get(f"/copilot/tickets/{ticket_id}/audit")
    assert r_audit.status_code == 200
    data_audit = r_audit.json()
    assert data_audit["is_valid"] is True
    assert data_audit["event_count"] >= 5
    assert len(data_audit["tamper_errors"]) == 0


def test_invalid_decision_returns_400() -> None:
    """Verifies invalid approval decision rejection."""
    ticket_id = "TICK-API-102"
    client.post(
        "/copilot/tickets/ingest",
        json={
            "ticket_id": ticket_id,
            "raw_text": "Gutschrift erbeten für PO-1001.",
            "order_id": "PO-1001",
        },
    )

    r = client.post(
        f"/copilot/tickets/{ticket_id}/approve",
        json={"decision": "maybe"},
    )
    assert r.status_code == 400
    assert "Invalid decision" in r.json()["detail"]


def test_unknown_ticket_audit_returns_404() -> None:
    """Verifies 404 on non-existent ticket audit request."""
    r = client.get("/copilot/tickets/TICK-NONEXISTENT/audit")
    assert r.status_code == 404
