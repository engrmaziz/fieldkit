"""Comprehensive tests for A/B Experiments catalog, traffic router, and results aggregation."""

from __future__ import annotations

import pytest
from fieldkit_tracehub.experiments import ExperimentEngine
from fieldkit_tracehub.main import app
from starlette.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_experiment_engine_crud_and_resolution() -> None:
    engine = ExperimentEngine()

    # Pre-seeded experiments
    experiments = engine.list_experiments()
    assert len(experiments) >= 2
    assert any(e.name == "rag_model_ab" for e in experiments)
    assert any(e.name == "broken_prompt_ab" for e in experiments)

    # Deterministic variant resolution
    var1, m1, p1 = engine.resolve_variant("rag_model_ab", user_id="jana")
    var2, m2, p2 = engine.resolve_variant("rag_model_ab", user_id="jana")
    # Same user must receive the exact same variant consistently
    assert var1 == var2
    assert m1 == m2
    assert p1 == p2
    assert var1 in ("control", "treatment_14b")

    # Check distribution across 100 simulated users
    counts: dict[str, int] = {}
    for i in range(100):
        v_name, _, _ = engine.resolve_variant("rag_model_ab", user_id=f"user_{i}")
        counts[v_name] = counts.get(v_name, 0) + 1
    # Both variants should receive substantial traffic on a 50/50 split
    assert counts.get("control", 0) > 30
    assert counts.get("treatment_14b", 0) > 30

    # Test unknown experiment fallback
    def_var, def_model, def_prompt = engine.resolve_variant("unknown_experiment", user_id="mehmet")
    assert def_var == "default"
    assert def_model == "qwen2.5:7b"


def test_experiment_engine_results_and_stop_rule() -> None:
    engine = ExperimentEngine()

    # Normal experiment results
    normal_res = engine.get_experiment_results("rag_model_ab")
    assert normal_res is not None
    assert normal_res.experiment_name == "rag_model_ab"
    assert len(normal_res.variants) == 2
    assert normal_res.stop_rule_triggered is False
    assert "satisfaction_rate" in normal_res.metric_deltas

    # Degraded experiment triggering safety stop rule
    degraded_res = engine.get_experiment_results("broken_prompt_ab")
    assert degraded_res is not None
    assert degraded_res.stop_rule_triggered is True
    assert degraded_res.stop_rule_reason is not None
    assert "SAFETY STOP RULE" in degraded_res.stop_rule_reason
    assert "broken_candidate_v3" in degraded_res.stop_rule_reason


def test_experiments_api_endpoints(client: TestClient) -> None:
    # 1. GET /experiments
    resp = client.get("/experiments")
    assert resp.status_code == 200
    exps = resp.json()
    assert isinstance(exps, list)
    assert any(e["name"] == "rag_model_ab" for e in exps)

    # 2. GET /experiments/{name}
    resp = client.get("/experiments/rag_model_ab")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "rag_model_ab"
    assert data["task"] == "assistant_rag_qa"
    assert len(data["variants"]) == 2

    # 3. GET /experiments/{name}/config
    resp = client.get("/experiments/rag_model_ab/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert cfg["name"] == "rag_model_ab"
    assert "variants" in cfg

    # 4. POST /experiments/{name}/resolve
    resolve_payload = {"user_id": "mehmet_01"}
    resp = client.post("/experiments/rag_model_ab/resolve", json=resolve_payload)
    assert resp.status_code == 200
    assigned = resp.json()
    assert assigned["user_id"] == "mehmet_01"
    assert assigned["variant_name"] in ("control", "treatment_14b")
    assert assigned["model"] in ("qwen2.5:7b", "qwen2.5:14b")

    # 5. GET /experiments/{name}/results
    resp = client.get("/experiments/rag_model_ab/results")
    assert resp.status_code == 200
    results = resp.json()
    assert results["experiment_name"] == "rag_model_ab"
    assert len(results["variants"]) == 2
    assert results["stop_rule_triggered"] is False

    # 6. Safety stop rule on broken prompt
    resp = client.get("/experiments/broken_prompt_ab/results")
    assert resp.status_code == 200
    broken_results = resp.json()
    assert broken_results["stop_rule_triggered"] is True

    # 7. POST /experiments (create custom)
    new_exp = {
        "name": "custom_sql_exp",
        "task": "assistant_sql_query",
        "variants": [
            {"name": "v1", "model": "qwen2.5-coder:7b", "prompt_version": "1.0.0", "pct": 70},
            {"name": "v2", "model": "qwen2.5-coder:14b", "prompt_version": "2.0.0", "pct": 30},
        ],
        "status": "active",
        "description": "Test SQL coder variants",
    }
    resp = client.post("/experiments", json=new_exp)
    assert resp.status_code == 200
    assert resp.json()["name"] == "custom_sql_exp"
