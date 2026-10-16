"""Unit tests for services/hello."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fieldkit_hello.main import EchoResponse, app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_echo_endpoint() -> None:
    with patch("fieldkit_hello.main.get_llm_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.structured_output_from_template.return_value = EchoResponse(
            text="Echo: Hello World"
        )
        mock_get_client.return_value = mock_client

        response = client.post("/echo", json={"input": "Hello World"})
        assert response.status_code == 200
        assert response.json() == {"text": "Echo: Hello World"}
