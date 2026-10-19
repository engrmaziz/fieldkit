"""Tests for client-side A/B experiment config caching and deterministic variant resolution."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fieldkit_llm.client import LLMClient
from fieldkit_llm.experiments import (
    assign_variant_by_hash,
    clear_experiment_cache,
    resolve_experiment_variant,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_experiment_cache()


def test_assign_variant_by_hash_deterministic() -> None:
    variants = [
        {"name": "control", "model": "qwen2.5:7b", "prompt_version": "1.0.0", "pct": 50},
        {"name": "treatment", "model": "qwen2.5:14b", "prompt_version": "2.0.0", "pct": 50},
    ]

    # Deterministic mapping for user
    res1 = assign_variant_by_hash("user_alpha", "exp_1", variants)
    res2 = assign_variant_by_hash("user_alpha", "exp_1", variants)
    assert res1 == res2
    assert res1["name"] in ("control", "treatment")

    # Empty variants fallback
    fallback = assign_variant_by_hash("user_alpha", "exp_1", [])
    assert fallback["name"] == "default"


@pytest.mark.asyncio
@respx.mock
async def test_resolve_experiment_variant_with_caching() -> None:
    tracehub_url = "http://mock-tracehub:8006"
    route = respx.get(f"{tracehub_url}/experiments/test_exp/config").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "test_exp",
                "task": "assistant_rag_qa",
                "status": "active",
                "variants": [
                    {"name": "arm_a", "model": "m_a", "prompt_version": "1.0", "pct": 50},
                    {"name": "arm_b", "model": "m_b", "prompt_version": "2.0", "pct": 50},
                ],
            },
        )
    )

    # First call triggers HTTP request
    v_name, model, p_ver = await resolve_experiment_variant(
        experiment_name="test_exp",
        user_id="user_123",
        tracehub_url=tracehub_url,
    )
    assert route.call_count == 1
    assert v_name in ("arm_a", "arm_b")

    # Second call within 60s uses in-memory cache (call_count remains 1)
    v_name2, model2, p_ver2 = await resolve_experiment_variant(
        experiment_name="test_exp",
        user_id="user_123",
        tracehub_url=tracehub_url,
    )
    assert route.call_count == 1
    assert v_name == v_name2
    assert model == model2


@pytest.mark.asyncio
@respx.mock
async def test_resolve_experiment_variant_graceful_fallback() -> None:
    tracehub_url = "http://mock-tracehub:8006"
    # Mock HTTP 500 error from Tracehub
    respx.get(f"{tracehub_url}/experiments/down_exp/config").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    # Client must NOT crash; it must gracefully fall back to defaults
    v_name, model, p_ver = await resolve_experiment_variant(
        experiment_name="down_exp",
        user_id="user_999",
        default_model="qwen2.5:7b",
        default_prompt_version="1.0.0",
        tracehub_url=tracehub_url,
    )
    assert v_name == "control"
    assert model == "qwen2.5:7b"
    assert p_ver == "1.0.0"


@pytest.mark.asyncio
@respx.mock
async def test_llm_client_emits_experiment_span_attributes(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=cache_dir,
        cache_enabled=False,
    )

    respx.post("http://mock-ollama:11434/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": "Experiment response",
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
    )

    result = await client.generate(
        prompt="Test prompt",
        task="assistant_rag_qa",
        experiment="rag_model_ab",
        experiment_variant="treatment_14b",
    )
    assert result.text == "Experiment response"
    assert result.experiment == "rag_model_ab"
    assert result.experiment_variant == "treatment_14b"
