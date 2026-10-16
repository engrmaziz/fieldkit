"""Unit tests for fieldkit_llm enforcing shared LLM rules."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from fieldkit_llm.client import LLMClient, LLMValidationError
from fieldkit_llm.prompts import PromptVersionError, load_and_render_prompt
from pydantic import BaseModel


class EchoSchema(BaseModel):
    message: str
    confidence: float


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "llm_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.mark.asyncio
@respx.mock
async def test_generate_success(tmp_cache: Path) -> None:
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=tmp_cache,
        cache_enabled=True,
    )

    route = respx.post("http://mock-ollama:11434/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": "Hello World",
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
    )

    result = await client.generate(
        prompt="Test prompt",
        task="test_task",
        prompt_version="1.0.0",
        model="qwen2.5:7b",
    )
    assert result.text == "Hello World"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert not result.cached
    assert result.prompt_version == "1.0.0"
    assert route.called

    # Second call should hit disk cache
    cached_result = await client.generate(
        prompt="Test prompt",
        task="test_task",
        prompt_version="1.0.0",
        model="qwen2.5:7b",
    )
    assert cached_result.text == "Hello World"
    assert cached_result.cached is True
    assert route.call_count == 1  # Route not called again


@pytest.mark.asyncio
@respx.mock
async def test_chat_bypasses_cache(tmp_cache: Path) -> None:
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=tmp_cache,
        cache_enabled=True,
    )

    route = respx.post("http://mock-ollama:11434/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={"response": "Chat reply", "prompt_eval_count": 5, "eval_count": 5},
        )
    )

    # First call with is_chat=True
    r1 = await client.generate(prompt="User message", is_chat=True)
    assert r1.text == "Chat reply"
    assert not r1.cached
    assert route.call_count == 1

    # Second identical call with is_chat=True MUST NOT hit cache (Rule 5)
    r2 = await client.generate(prompt="User message", is_chat=True)
    assert r2.text == "Chat reply"
    assert not r2.cached
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_generate_retry_on_failure(tmp_cache: Path) -> None:
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=tmp_cache,
        cache_enabled=False,
    )

    route = respx.post("http://mock-ollama:11434/api/generate")
    route.side_effect = [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(
            200, json={"response": "Recovered", "prompt_eval_count": 2, "eval_count": 2}
        ),
    ]

    result = await client.generate(prompt="Retry test", max_retries=2)
    assert result.text == "Recovered"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_structured_output_success(tmp_cache: Path) -> None:
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=tmp_cache,
        cache_enabled=False,
    )

    respx.post("http://mock-ollama:11434/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": json.dumps({"message": "Valid schema", "confidence": 0.99}),
                "prompt_eval_count": 15,
                "eval_count": 10,
            },
        )
    )

    output = await client.structured_output(prompt="Generate structured", response_model=EchoSchema)
    assert isinstance(output, EchoSchema)
    assert output.message == "Valid schema"
    assert output.confidence == 0.99


@pytest.mark.asyncio
@respx.mock
async def test_structured_output_fail_closed_after_retry(tmp_cache: Path) -> None:
    """Rule 2: Retry once with validation error appended, then fail closed."""
    client = LLMClient(
        base_url="http://mock-ollama:11434",
        cache_dir=tmp_cache,
        cache_enabled=False,
    )

    # Both initial and retry response return invalid JSON (missing required field 'confidence')
    route = respx.post("http://mock-ollama:11434/api/generate")
    route.side_effect = [
        httpx.Response(200, json={"response": json.dumps({"message": "missing confidence field"})}),
        httpx.Response(200, json={"response": json.dumps({"message": "still missing confidence"})}),
    ]

    with pytest.raises(LLMValidationError) as exc_info:
        await client.structured_output(
            prompt="Generate broken",
            response_model=EchoSchema,
            task="test_fail_closed",
        )

    assert "Failing closed" in str(exc_info.value)
    assert route.call_count == 2


def test_prompt_template_with_version_header(tmp_path: Path) -> None:
    template_file = tmp_path / "test_prompt.jinja"
    template_file.write_text(
        "{# version: 2.1.0 #}\nAnalyze customer: {{ customer_name }} for plant {{ plant_code }}.",
        encoding="utf-8",
    )

    rendered = load_and_render_prompt(
        template_file,
        customer_name="Halden Industrie",
        plant_code="DE-HAM",
    )
    assert rendered.version == "2.1.0"
    assert rendered.text == "Analyze customer: Halden Industrie for plant DE-HAM."


def test_prompt_template_missing_version_raises(tmp_path: Path) -> None:
    template_file = tmp_path / "invalid_prompt.jinja"
    template_file.write_text("Hello {{ name }} without version header.", encoding="utf-8")

    with pytest.raises(PromptVersionError):
        load_and_render_prompt(template_file, name="Jana")
