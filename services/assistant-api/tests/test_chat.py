"""Tests for assistant chat endpoints and streaming SSE."""

from fastapi.testclient import TestClient
from fieldkit_assistant.main import app
from fieldkit_common.auth import Principal, get_current_principal

client = TestClient(app)


def test_chat_endpoint_grounded_answer() -> None:
    """Verify that an authorized user receives a grounded answer with citations."""
    mehmet = Principal(sub="mehmet-1", username="mehmet", roles=["quality"], plant="DE-HAM")
    app.dependency_overrides[get_current_principal] = lambda: mehmet

    try:
        response = client.post(
            "/api/assistant/chat",
            json={
                "query": "What is the surface roughness tolerance for honing hydraulic cylinders in Hamburg?",
                "top_k": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert data["insufficient"] is False
        assert len(data["citations"]) > 0
        assert data["is_grounded"] is True
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
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["insufficient"] is True
        assert "not found in the documents you are authorized to access" in data["answer"]
        assert len(data["citations"]) == 0
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_sse() -> None:
    """Verify Server-Sent Events stream emits sources, answer tokens, and verification."""
    jana = Principal(sub="jana-1", username="jana", roles=["admin"], plant=None)
    app.dependency_overrides[get_current_principal] = lambda: jana

    try:
        response = client.post(
            "/api/assistant/chat/stream",
            json={
                "query": "What machine guarding is required under OSHA regulations?",
                "top_k": 3,
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: sources" in body
        assert "event: answer" in body
        assert "event: verification" in body
        assert "event: done" in body
    finally:
        app.dependency_overrides.clear()
