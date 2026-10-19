"""Unit tests for Tracehub healthz and readyz endpoints."""

import pytest
from fastapi.testclient import TestClient
from fieldkit_tracehub.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_tracehub_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "tracehub"
    assert data["version"] == "0.1.0"


def test_tracehub_readyz(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "tracehub"


def test_tracehub_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Tracehub" in data["service"]
    assert data["docs"] == "/docs"
