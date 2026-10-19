"""Unit and contract tests for Tracehub trace search and metrics API."""

import pytest
from fastapi.testclient import TestClient
from fieldkit_tracehub.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_traces_default(client: TestClient) -> None:
    resp = client.get("/traces?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data
    assert "total" in data
    assert len(data["traces"]) <= 10
    if data["traces"]:
        t = data["traces"][0]
        assert "trace_id" in t
        assert "root_span_name" in t
        assert "service" in t
        assert "duration_ms" in t
        assert "status" in t


def test_list_traces_filtered_service(client: TestClient) -> None:
    resp = client.get("/traces?service=assistant-api&limit=15")
    assert resp.status_code == 200
    data = resp.json()
    for t in data["traces"]:
        assert t["service"] == "assistant-api"


def test_list_traces_filtered_status(client: TestClient) -> None:
    resp = client.get("/traces?status=ERROR&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for t in data["traces"]:
        assert t["status"] == "ERROR"


def test_get_trace_tree(client: TestClient) -> None:
    # First get a trace_id from search
    list_resp = client.get("/traces?limit=1")
    assert list_resp.status_code == 200
    traces = list_resp.json().get("traces", [])
    assert len(traces) > 0
    test_id = traces[0]["trace_id"]

    # Now fetch its waterfall tree
    tree_resp = client.get(f"/traces/{test_id}")
    assert tree_resp.status_code == 200
    tree_data = tree_resp.json()
    assert tree_data["trace_id"] == test_id
    assert tree_data["total_spans"] >= 1
    assert tree_data["root"] is not None
    root = tree_data["root"]
    assert "name" in root
    assert "duration_ms" in root
    assert "children" in root


def test_get_metrics_latency_p95(client: TestClient) -> None:
    resp = client.get("/metrics?series=latency_p95&service=assistant-api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["series_name"] == "latency_p95"
    assert "points" in data
    assert len(data["points"]) > 0
    p0 = data["points"][0]
    assert "timestamp" in p0
    assert "value" in p0
    assert p0["value"] > 0


def test_get_metrics_error_rate(client: TestClient) -> None:
    resp = client.get("/metrics?series=error_rate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["series_name"] == "error_rate"
    assert len(data["points"]) > 0


def test_get_metrics_tokens_per_min(client: TestClient) -> None:
    resp = client.get("/metrics?series=tokens_per_min")
    assert resp.status_code == 200
    data = resp.json()
    assert data["series_name"] == "tokens_per_min"
    assert len(data["points"]) > 0
