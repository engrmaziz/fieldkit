"""Integration tests for the Human-in-the-Loop Review Queue API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_foundry.main import app


def test_review_queue_lifecycle():
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="jana_id",
        username="jana",
        roles=["admin"],
        plant="DE-HAM",
    )

    client = TestClient(app)

    # 1. List pending items
    resp_list = client.get("/review-queue")
    assert resp_list.status_code == 200
    data = resp_list.json()
    assert data["count"] >= 2
    pair_ids = [item["pair_id"] for item in data["items"]]
    assert "pair-001" in pair_ids

    # 2. Submit match decision on pair-001
    resp_match = client.post(
        "/review-queue/pair-001",
        json={"decision": "match", "comment": "Verified legal entity continuity"},
    )
    assert resp_match.status_code == 200
    res_match = resp_match.json()
    assert res_match["status"] == "RESOLVED"
    assert res_match["decision"] == "match"
    assert len(res_match["affected_clusters"]) == 1
    assert "canonical_cluster_" in res_match["affected_clusters"][0]

    # 3. Submit non-match decision on pair-002
    resp_non_match = client.post(
        "/review-queue/pair-002",
        json={"decision": "non_match", "comment": "Different corporate legal entities"},
    )
    assert resp_non_match.status_code == 200
    res_non_match = resp_non_match.json()
    assert res_non_match["status"] == "RESOLVED"
    assert res_non_match["decision"] == "non_match"
    assert len(res_non_match["affected_clusters"]) == 2

    # 4. Non-existent pair returns 404
    resp_404 = client.post("/review-queue/pair-999-unknown", json={"decision": "match"})
    assert resp_404.status_code == 404

    app.dependency_overrides.clear()
