"""Unit tests for response cache and feedback endpoint."""

import time

from fastapi.testclient import TestClient
from fieldkit_assistant.cache import ResponseCache, compute_cache_key
from fieldkit_assistant.main import app
from fieldkit_common.auth import Principal, get_current_principal


def test_compute_cache_key_normalization() -> None:
    p1 = Principal(sub="elena-1", username="elena", roles=["procurement"], plant="Hamburg")

    # Queries differing only by case, punctuation, or spaces must produce identical key
    k1 = compute_cache_key("How many purchase orders in Q3 2026?", p1)
    k2 = compute_cache_key("  how many purchase orders in q3 2026?   ", p1)
    k3 = compute_cache_key("how   many purchase orders in q3 2026", p1)
    assert k1 == k2 == k3


def test_compute_cache_key_scope_isolation() -> None:
    p_hamburg = Principal(sub="elena-1", username="elena", roles=["quality"], plant="Hamburg")
    p_munich = Principal(sub="mehmet-1", username="mehmet", roles=["quality"], plant="Munich")
    p_admin = Principal(sub="sofia-1", username="sofia", roles=["admin"], plant=None)

    q = "What is the defect rate on valves?"
    k_hamburg = compute_cache_key(q, p_hamburg)
    k_munich = compute_cache_key(q, p_munich)
    k_admin = compute_cache_key(q, p_admin)

    # Different plants or roles MUST have distinct cache keys
    assert k_hamburg != k_munich
    assert k_hamburg != k_admin
    assert k_munich != k_admin


def test_response_cache_get_set_and_expiry() -> None:
    cache = ResponseCache(default_ttl_seconds=1)
    cache.set("key-1", {"answer": "Valves defect rate is 1.2%"})
    assert cache.get("key-1") == {"answer": "Valves defect rate is 1.2%"}

    # Invalidate
    assert cache.invalidate("key-1") is True
    assert cache.get("key-1") is None

    # Expiration
    cache.set("key-2", {"answer": "Expiring answer"}, ttl_seconds=0.1)
    time.sleep(0.15)
    assert cache.get("key-2") is None


def test_feedback_endpoint() -> None:
    test_principal = Principal(sub="elena-1", username="elena", roles=["quality"], plant="Hamburg")
    app.dependency_overrides[get_current_principal] = lambda: test_principal

    try:
        client = TestClient(app)
        payload = {
            "trace_id": "trace-test-12345",
            "thumbs": "up",
            "comment": "Accurate SQL query and clear table output.",
            "route": "sql",
            "query": "Top 5 suppliers by late deliveries",
        }
        resp = client.post("/api/assistant/feedback", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recorded"
        assert "id" in data
        assert "timestamp" in data
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
