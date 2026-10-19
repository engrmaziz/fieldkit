"""Tests for unified assistant chat endpoints and streaming SSE."""

from fastapi.testclient import TestClient
from fieldkit_assistant.main import app
from fieldkit_common.auth import Principal, get_current_principal

client = TestClient(app)


def test_chat_endpoint_grounded_answer() -> None:
    """Verify that an authorized user receives a grounded answer with citations via RAG route."""
    mehmet = Principal(sub="mehmet-1", username="mehmet", roles=["quality"], plant="DE-HAM")
    app.dependency_overrides[get_current_principal] = lambda: mehmet

    try:
        response = client.post(
            "/api/assistant/chat",
            json={
                "query": "What is the surface roughness tolerance for honing hydraulic cylinders in Hamburg?",
                "top_k": 3,
                "route": "rag",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["route"] == "rag"
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert len(data["citations"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_refusal_for_unauthorized_scope() -> None:
    """Verify that cross-plant or restricted legal queries return safe refusal with 0 leaks."""
    lukas = Principal(sub="lukas-1", username="lukas", roles=["support"], plant="DE-STR")
    app.dependency_overrides[get_current_principal] = lambda: lukas

    try:
        response = client.post(
            "/api/assistant/chat",
            json={
                "query": "Show me the confidential legal arbitration agreements and executive dispute liabilities.",
                "top_k": 3,
                "route": "rag",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "not found in the documents you are authorized to access" in data["answer"]
        assert len(data["citations"]) == 0
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_sql_route() -> None:
    """Verify that an operational query is routed to SQL and returns tabular results."""
    elena = Principal(sub="elena-1", username="elena", roles=["procurement"], plant="Hamburg")
    app.dependency_overrides[get_current_principal] = lambda: elena

    try:
        response = client.post(
            "/api/assistant/chat",
            json={
                "query": "How many purchase orders were issued in Q3 2026?",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["route"] == "sql"
        assert data["sql"] is not None
        assert "SELECT" in data["sql"].upper()
        assert len(data["columns"]) > 0
        assert data["row_count"] >= 0
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_both_route() -> None:
    """Verify that a hybrid query routes to 'both' and synthesizes data + policy context."""
    sofia = Principal(sub="sofia-1", username="sofia", roles=["admin"], plant=None)
    app.dependency_overrides[get_current_principal] = lambda: sofia

    try:
        response = client.post(
            "/api/assistant/chat",
            json={
                "query": "What is our defect rate on hydraulic valves and what does our SOP require for defective lots?",
                "top_k": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["route"] == "both"
        assert "Operational Data Findings" in data["answer"]
        assert "Regulatory & Policy Context" in data["answer"]
        assert data["sql"] is not None
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_sse() -> None:
    """Verify Server-Sent Events stream emits route, sources, tokens, and done."""
    jana = Principal(sub="jana-1", username="jana", roles=["admin"], plant=None)
    app.dependency_overrides[get_current_principal] = lambda: jana

    try:
        response = client.post(
            "/api/assistant/chat/stream",
            json={
                "query": "What machine guarding is required under OSHA regulations?",
                "top_k": 3,
                "route": "rag",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: route" in body
        assert "event: sources" in body
        assert "event: token" in body
        assert "event: done" in body
    finally:
        app.dependency_overrides.clear()


def test_chat_caching_and_bypass() -> None:
    """Verify that exact-match cache returns cached=True on repeat queries, and bypass skips it."""
    sofia = Principal(sub="sofia-1", username="sofia", roles=["admin"], plant=None)
    app.dependency_overrides[get_current_principal] = lambda: sofia

    try:
        q = "Top 5 suppliers by late deliveries to Hamburg"
        # Call 1: Miss
        r1 = client.post("/api/assistant/chat", json={"query": q})
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["cached"] is False

        # Call 2: Hit
        r2 = client.post("/api/assistant/chat", json={"query": q})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["cached"] is True
        assert d2["sql"] == d1["sql"]

        # Call 3: Bypass via Header
        r3 = client.post(
            "/api/assistant/chat",
            json={"query": q},
            headers={"X-Cache-Bypass": "true"},
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["cached"] is False
    finally:
        app.dependency_overrides.clear()
