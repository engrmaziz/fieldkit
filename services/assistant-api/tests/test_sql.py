"""Tests for assistant NL2SQL API endpoint."""

from fastapi.testclient import TestClient
from fieldkit_assistant.main import app
from fieldkit_common.auth import Principal, get_current_principal

client = TestClient(app)


def test_sql_endpoint_success() -> None:
    """Verify that an authorized user can generate and execute safe SQL from natural language."""
    mehmet = Principal(sub="mehmet-1", username="mehmet", roles=["quality"], plant="DE-HAM")
    app.dependency_overrides[get_current_principal] = lambda: mehmet

    try:
        response = client.post(
            "/api/assistant/sql",
            json={
                "query": "List all suppliers located in Germany.",
                "execute": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "sql" in data
        assert data["sql"].upper().startswith("SELECT")
        assert data["validation"]["is_valid"] is True
        assert "suppliers" in data["tables_used"]
        assert data["execution"] is not None
        assert len(data["execution"]["rows"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_sql_endpoint_complex_analytical_query() -> None:
    """Verify that complex analytical join queries are generated and validated."""
    sofia = Principal(sub="sofia-1", username="sofia", roles=["procurement"], plant=None)
    app.dependency_overrides[get_current_principal] = lambda: sofia

    try:
        response = client.post(
            "/api/assistant/sql",
            json={
                "query": "Show quality incidents with critical severity for plant Stuttgart",
                "execute": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["validation"]["is_valid"] is True
        assert "quality_incidents" in data["tables_used"]
        assert "LIMIT" in data["sql"].upper()
    finally:
        app.dependency_overrides.clear()


def test_sql_endpoint_unauthenticated() -> None:
    """Verify that requests with invalid credentials return 401 Unauthorized."""
    app.dependency_overrides.clear()
    response = client.post(
        "/api/assistant/sql",
        json={"query": "SELECT * FROM suppliers;"},
        headers={"Authorization": "Bearer invalid_malformed_jwt"},
    )
    assert response.status_code == 401
