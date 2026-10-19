"""Comprehensive tests for Prompt Registry, Version Diffing, and Eval Comparison Engine."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fieldkit_tracehub.eval_engine import EvalEngine
from fieldkit_tracehub.main import app
from fieldkit_tracehub.prompt_registry import PromptRegistry
from fieldkit_tracehub.schemas import (
    EvalItem,
    EvalRunCreate,
    PromptCreate,
)
from starlette.testclient import TestClient

from scripts.publish_prompts import find_prompt_files, parse_prompt_file


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_prompt_registry_crud_and_diff() -> None:
    registry = PromptRegistry()

    # Pre-seeded prompts
    prompts = registry.list_prompts()
    assert any(p.name == "rag_answer" for p in prompts)
    rag_summary = next(p for p in prompts if p.name == "rag_answer")
    assert rag_summary.active_version == "2.0.0"
    assert "1.0.0" in rag_summary.versions
    assert "2.0.0" in rag_summary.versions

    # Diff between pre-seeded v1 and v2
    diff = registry.diff_prompt("rag_answer", "1.0.0", "2.0.0")
    assert diff is not None
    assert diff.name == "rag_answer"
    assert diff.v1 == "1.0.0"
    assert diff.v2 == "2.0.0"
    assert diff.additions > 0
    assert "DIN EN ISO" in diff.diff_text

    # Register a new version 3.0.0
    v3_text = "{# version: 3.0.0 #}\nUpdated Halden prompt with strict zero hallucination."
    v3_sha = hashlib.sha256(v3_text.encode("utf-8")).hexdigest()
    rec = registry.register_prompt(
        PromptCreate(
            name="rag_answer",
            version="3.0.0",
            template=v3_text,
            sha256=v3_sha,
            package="fieldkit_retrieval",
        )
    )
    assert rec.version == "3.0.0"
    assert rec.sha256 == v3_sha

    # Verify latest returns v3
    latest = registry.get_prompt("rag_answer")
    assert latest is not None
    assert latest.version == "3.0.0"

    # Specific version retrieval
    v1 = registry.get_prompt("rag_answer", version="1.0.0")
    assert v1 is not None
    assert v1.version == "1.0.0"

    # Non-existent prompt
    assert registry.get_prompt("unknown_prompt") is None
    assert registry.diff_prompt("unknown_prompt", "1.0.0", "2.0.0") is None


def test_eval_engine_and_bootstrap_ci() -> None:
    engine = EvalEngine()

    runs = engine.list_eval_runs()
    assert len(runs) >= 2
    assert any(r.run_id == "run-p2-v1-baseline" for r in runs)
    assert any(r.run_id == "run-p2-v2-candidate" for r in runs)

    # Compare baseline vs candidate
    comp = engine.compare_eval_runs("run-p2-v1-baseline", "run-p2-v2-candidate")
    assert comp is not None
    assert comp.baseline_id == "run-p2-v1-baseline"
    assert comp.candidate_id == "run-p2-v2-candidate"
    assert comp.total_items_compared == 4
    assert comp.total_regressions >= 1
    assert comp.total_improvements >= 1

    # Check metric deltas with bootstrap CI
    assert "faithfulness" in comp.metric_deltas
    assert "citation_accuracy" in comp.metric_deltas

    delta_cite = comp.metric_deltas["citation_accuracy"]
    assert delta_cite.delta > 0
    assert delta_cite.candidate_score >= delta_cite.baseline_score

    # Item regressions must capture the dropped item
    regressed_ids = [r.item_id for r in comp.regressions]
    assert "q-003" in regressed_ids
    reg_item = next(r for r in comp.regressions if r.item_id == "q-003")
    assert reg_item.delta < 0
    assert reg_item.baseline_score > reg_item.candidate_score


def test_eval_engine_custom_run_storage() -> None:
    engine = EvalEngine()

    items = [
        EvalItem(id="item-1", question="Q1", scores={"score": 0.5}, passed=True),
        EvalItem(id="item-2", question="Q2", scores={"score": 0.8}, passed=True),
    ]
    custom_run = engine.store_eval_run(
        EvalRunCreate(
            run_id="run-custom-test",
            suite="test_suite",
            model="ollama:mock",
            prompt_versions={"mock": "1.0"},
            items=items,
            aggregates={"score": 0.65},
        )
    )
    assert custom_run.run_id == "run-custom-test"
    assert custom_run.total_items == 2

    retrieved = engine.get_eval_run("run-custom-test")
    assert retrieved is not None
    assert retrieved.aggregates["score"] == 0.65


def test_prompts_api_endpoints(client: TestClient) -> None:
    # 1. GET /prompts
    resp = client.get("/prompts")
    assert resp.status_code == 200
    summaries = resp.json()
    assert isinstance(summaries, list)
    assert any(s["name"] == "rag_answer" for s in summaries)

    # 2. GET /prompts/{name}
    resp = client.get("/prompts/rag_answer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "rag_answer"

    # Specific version
    resp = client.get("/prompts/rag_answer?version=1.0.0")
    assert resp.status_code == 200
    assert resp.json()["version"] == "1.0.0"

    # 404 for unknown version
    resp = client.get("/prompts/rag_answer?version=99.9.9")
    assert resp.status_code == 404

    # 3. GET /prompts/{name}/diff
    resp = client.get("/prompts/rag_answer/diff?v1=1.0.0&v2=2.0.0")
    assert resp.status_code == 200
    diff_data = resp.json()
    assert diff_data["name"] == "rag_answer"
    assert diff_data["v1"] == "1.0.0"
    assert diff_data["v2"] == "2.0.0"
    assert "diff_text" in diff_data
    assert diff_data["additions"] >= 1

    # 4. POST /prompts
    template_str = "{# version: 1.1.0 #}\nTest prompt template."
    create_payload = {
        "name": "unit_test_prompt",
        "version": "1.1.0",
        "template": template_str,
        "sha256": hashlib.sha256(template_str.encode("utf-8")).hexdigest(),
        "package": "fieldkit_test",
    }
    resp = client.post("/prompts", json=create_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "unit_test_prompt"
    assert resp.json()["version"] == "1.1.0"


def test_evals_api_endpoints(client: TestClient) -> None:
    # 1. GET /eval-runs
    resp = client.get("/eval-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) >= 2

    # Filter by suite
    resp = client.get("/eval-runs?suite=assistant_rag")
    assert resp.status_code == 200
    assert all(r["suite"] == "assistant_rag" for r in resp.json())

    # 2. GET /eval-runs/{run_id}
    resp = client.get("/eval-runs/run-p2-v1-baseline")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["run_id"] == "run-p2-v1-baseline"
    assert len(detail["items"]) == 4

    # 404 for unknown run
    resp = client.get("/eval-runs/nonexistent-run-id")
    assert resp.status_code == 404

    # 3. GET /eval-runs/compare
    resp = client.get("/eval-runs/compare?baseline_id=run-p2-v1-baseline&candidate_id=run-p2-v2-candidate")
    assert resp.status_code == 200
    comp = resp.json()
    assert comp["baseline_id"] == "run-p2-v1-baseline"
    assert comp["candidate_id"] == "run-p2-v2-candidate"
    assert "metric_deltas" in comp
    assert len(comp["regressions"]) >= 1

    # Compare non-existent returns 404
    resp = client.get("/eval-runs/compare?baseline_id=run-p2-v1-baseline&candidate_id=does-not-exist")
    assert resp.status_code == 404

    # 4. POST /eval-runs
    new_run = {
        "run_id": "run-api-test-01",
        "suite": "api_test_suite",
        "model": "test-model",
        "prompt_versions": {"p": "1.0"},
        "git_sha": "testsha",
        "items": [
            {
                "id": "i1",
                "question": "Question 1",
                "scores": {"acc": 1.0},
                "output": "Answer 1",
                "trace_id": "trc-test",
                "passed": True,
            }
        ],
        "aggregates": {"acc": 1.0},
    }
    resp = client.post("/eval-runs", json=new_run)
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run-api-test-01"


def test_publish_prompts_script_parsing(tmp_path: Path) -> None:
    prompt_file = tmp_path / "test_prompt.jinja"
    prompt_file.write_text("{# version: 4.2.1 #}\nHello {{ name }}!", encoding="utf-8")

    parsed = parse_prompt_file(prompt_file)
    assert parsed is not None
    assert parsed["name"] == "test_prompt"
    assert parsed["version"] == "4.2.1"
    assert "Hello {{ name }}!" in parsed["template"]
    assert len(parsed["sha256"]) == 64

    # Scan
    found = find_prompt_files(tmp_path)
    assert len(found) == 1
    assert found[0] == prompt_file
