"""Unit and integration tests for Mock ERP service."""

from fastapi.testclient import TestClient
from fieldkit_mock_erp.main import app

client = TestClient(app)


def test_healthz_and_readyz() -> None:
    """Verifies service health probes."""
    r_h = client.get("/healthz")
    assert r_h.status_code == 200
    assert r_h.json()["status"] == "healthy"

    r_r = client.get("/readyz")
    assert r_r.status_code == 200
    assert r_r.json()["status"] == "ready"


def test_get_order_and_shipments() -> None:
    """Verifies order retrieval and logistics tracking."""
    # Existing order
    resp = client.get("/orders/PO-1001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == "PO-1001"
    assert data["customer_id"] == "CUST-001"
    assert data["status"] == "delivered"
    assert len(data["items"]) > 0

    # Non-existent order
    resp_404 = client.get("/orders/PO-UNKNOWN")
    assert resp_404.status_code == 404

    # Shipments
    resp_shp = client.get("/shipments/PO-1001")
    assert resp_shp.status_code == 200
    shps = resp_shp.json()
    assert len(shps) == 1
    assert shps[0]["tracking_number"] == "DHL-DE-994821"


def test_get_customer_and_legal_hold() -> None:
    """Verifies customer query and legal hold flag representation."""
    # Standard customer
    resp_std = client.get("/customers/CUST-001")
    assert resp_std.status_code == 200
    assert resp_std.json()["legal_hold"] is False

    # Legal hold customer
    resp_hold = client.get("/customers/CUST-003")
    assert resp_hold.status_code == 200
    assert resp_hold.json()["legal_hold"] is True


def test_rma_idempotency_and_conflict() -> None:
    """Verifies strict idempotency replay and 409 Conflict on payload mismatch."""
    idem_key = "ticket-991:rma-1"
    payload = {
        "order_id": "PO-1001",
        "reason": "Leaking seal on valve body",
        "items": [{"part_id": "HX-400", "quantity": 1, "defect_description": "Oil seepage"}],
    }

    # 1. First execution
    r1 = client.post("/rma", json=payload, headers={"Idempotency-Key": idem_key})
    assert r1.status_code == 201
    d1 = r1.json()
    assert d1["approved"] is True
    assert "RMA-" in d1["rma_id"]

    # 2. Idempotent replay: identical key + identical body -> identical result
    r2 = client.post("/rma", json=payload, headers={"Idempotency-Key": idem_key})
    assert r2.status_code == 201
    d2 = r2.json()
    assert d2["rma_id"] == d1["rma_id"]
    assert d2["created_at"] == d1["created_at"]

    # 3. Conflict: same key + DIFFERENT body -> 409 Conflict
    conflicting_payload = {
        "order_id": "PO-1001",
        "reason": "Different reason entirely",
        "items": [{"part_id": "HX-400", "quantity": 2, "defect_description": "Completely broken"}],
    }
    r3 = client.post("/rma", json=conflicting_payload, headers={"Idempotency-Key": idem_key})
    assert r3.status_code == 409
    assert "collision" in r3.json()["detail"].lower()


def test_credit_idempotency_and_conflict() -> None:
    """Verifies credit idempotency replay and 409 Conflict on amount mismatch."""
    idem_key = "ticket-442:credit-1"
    payload = {
        "order_id": "PO-1001",
        "amount_eur": 150.0,
        "reason": "Customer courtesy discount for 1-day shipment delay",
    }

    # 1. First execution
    r1 = client.post("/credits", json=payload, headers={"Idempotency-Key": idem_key})
    assert r1.status_code == 201
    d1 = r1.json()
    assert d1["amount_eur"] == 150.0

    # 2. Idempotent replay
    r2 = client.post("/credits", json=payload, headers={"Idempotency-Key": idem_key})
    assert r2.status_code == 201
    d2 = r2.json()
    assert d2["credit_id"] == d1["credit_id"]

    # 3. Conflict: same key + different amount
    conflicting_payload = {
        "order_id": "PO-1001",
        "amount_eur": 300.0,
        "reason": "Customer courtesy discount",
    }
    r3 = client.post("/credits", json=conflicting_payload, headers={"Idempotency-Key": idem_key})
    assert r3.status_code == 409


def test_simulated_503_error_injection() -> None:
    """Verifies that transient 503 is returned when simulated."""
    resp = client.post(
        "/rma?inject_503=true",
        json={"order_id": "PO-1001", "reason": "Test 503", "items": []},
    )
    assert resp.status_code == 503
    assert "transient" in resp.json()["detail"].lower()
