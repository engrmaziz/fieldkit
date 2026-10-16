"""Unified async Ollama client wrapper enforcing Fieldkit LLM rules.

Fieldkit LLM Rules:
1. One client: packages/llm. Every call has task name, model, prompt_version, timeout (default 60s),
   and emits an OTel span P7 consumes.
2. Structured output only for anything machine-consumed: pass Pydantic JSON schema as Ollama format;
   on validation failure retry once with validation error appended, then fail closed.
3. Temperature 0 for extraction, SQL, classification; seed fixed in evals for reproducibility.
4. Prompts live in packages/*/prompts/*.jinja with a version header, never inline strings.
5. Cache: exact-match disk cache in dev and evals; disabled for user-facing chat.
"""

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeVar

import httpx
from fieldkit_common.logging import get_logger
from fieldkit_common.settings import get_common_settings
from opentelemetry import trace
from pydantic import BaseModel, ValidationError

from .prompts import load_and_render_prompt

logger = get_logger("fieldkit.llm")
tracer = trace.get_tracer("fieldkit.llm")

T = TypeVar("T", bound=BaseModel)


class LLMValidationError(RuntimeError):
    """Raised when structured LLM output fails schema validation and fails closed."""

    def __init__(self, message: str, raw_text: str, errors: Any) -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.errors = errors


class LLMResult(BaseModel):
    """Result of an LLM generation."""

    text: str
    model: str
    task: str
    prompt_version: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached: bool = False


class LLMClient:
    """Production-grade local LLM client for Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        default_timeout: float = 60.0,
        cache_dir: str | Path = "./.cache/llm",
        cache_enabled: bool = True,
    ) -> None:
        settings = get_common_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_model_default
        self.default_timeout = default_timeout or float(settings.ollama_timeout_seconds)
        self.cache_dir = Path(cache_dir)
        self.cache_enabled = cache_enabled

        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(
        self,
        model: str,
        task: str,
        prompt_version: str,
        prompt: str,
        system: str | None,
        temperature: float,
        seed: int | None,
        format_param: Any,
    ) -> str:
        payload = {
            "model": model,
            "task": task,
            "prompt_version": prompt_version,
            "prompt": prompt,
            "system": system or "",
            "temperature": temperature,
            "seed": seed,
            "format": format_param,
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _get_cache(self, key: str, is_chat: bool) -> LLMResult | None:
        # Rule 5: Cache disabled for user-facing chat
        if is_chat or not self.cache_enabled:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                data["cached"] = True
                return LLMResult(**data)
            except Exception as exc:
                logger.warning("failed_to_read_cache", error=str(exc))
        return None

    def _set_cache(self, key: str, result: LLMResult, is_chat: bool) -> None:
        # Rule 5: Cache disabled for user-facing chat
        if is_chat or not self.cache_enabled:
            return
        cache_file = self.cache_dir / f"{key}.json"
        try:
            cache_file.write_text(result.model_dump_json(), encoding="utf-8")
        except Exception as exc:
            logger.warning("failed_to_write_cache", error=str(exc))

    async def generate(
        self,
        prompt: str,
        task: str = "llm_generate",
        prompt_version: str = "1.0.0",
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        timeout: float | None = None,
        format_param: Any | None = None,
        max_retries: int = 3,
        is_chat: bool = False,
    ) -> LLMResult:
        """Call Ollama /api/generate with retries, jitter, tracing, and caching.

        Enforces:
        - OTel span with task, model, prompt_version, latency, and tokens
        - Temperature 0 default for extraction/SQL/classification
        - Seed passing for reproducible evals
        - Cache bypass for user-facing chat
        """
        target_model = model or self.default_model
        target_timeout = timeout or self.default_timeout

        cache_key = self._cache_key(
            model=target_model,
            task=task,
            prompt_version=prompt_version,
            prompt=prompt,
            system=system,
            temperature=temperature,
            seed=seed,
            format_param=format_param,
        )

        cached_result = self._get_cache(cache_key, is_chat=is_chat)
        if cached_result:
            return cached_result

        with tracer.start_as_current_span(f"llm.{task}") as span:
            span.set_attribute("llm.task", task)
            span.set_attribute("llm.model", target_model)
            span.set_attribute("llm.prompt_version", prompt_version)
            span.set_attribute("llm.temperature", temperature)
            span.set_attribute("llm.timeout_seconds", target_timeout)
            span.set_attribute("llm.is_chat", is_chat)
            if seed is not None:
                span.set_attribute("llm.seed", seed)

            options: dict[str, Any] = {"temperature": temperature}
            if seed is not None:
                options["seed"] = seed

            req_payload: dict[str, Any] = {
                "model": target_model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            }
            if system:
                req_payload["system"] = system
            if format_param is not None:
                req_payload["format"] = format_param

            last_error: Exception | None = None
            start_time = time.perf_counter()

            for attempt in range(1, max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=target_timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/api/generate",
                            json=req_payload,
                        )
                        response.raise_for_status()
                        data = response.json()

                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    output_text = data.get("response", "")
                    prompt_eval_count = data.get("prompt_eval_count", 0)
                    eval_count = data.get("eval_count", 0)

                    span.set_attribute("llm.prompt_tokens", prompt_eval_count)
                    span.set_attribute("llm.completion_tokens", eval_count)
                    span.set_attribute("llm.latency_ms", elapsed_ms)
                    span.set_attribute("llm.cached", False)

                    result = LLMResult(
                        text=output_text,
                        model=target_model,
                        task=task,
                        prompt_version=prompt_version,
                        latency_ms=elapsed_ms,
                        prompt_tokens=prompt_eval_count,
                        completion_tokens=eval_count,
                        cached=False,
                    )
                    self._set_cache(cache_key, result, is_chat=is_chat)
                    return result

                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt < max_retries:
                        backoff = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.05, 0.2)
                        logger.warning(
                            "llm_call_retry",
                            task=task,
                            attempt=attempt,
                            backoff_seconds=backoff,
                            error=str(exc),
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            "llm_call_exhausted", task=task, attempts=max_retries, error=str(exc)
                        )

            raise RuntimeError(f"Ollama call failed after {max_retries} attempts: {last_error}")

    async def structured_output(
        self,
        prompt: str,
        response_model: type[T],
        task: str = "llm_structured",
        prompt_version: str = "1.0.0",
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        timeout: float | None = None,
        is_chat: bool = False,
    ) -> T:
        """Enforce strict structured output using Pydantic JSON schema.

        Rule 2: Pass Pydantic schema as Ollama format; on validation failure retry once
        with validation error appended, then fail closed (raise LLMValidationError).
        """
        schema = response_model.model_json_schema()

        first_res = await self.generate(
            prompt=prompt,
            task=task,
            prompt_version=prompt_version,
            model=model,
            system=system,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            format_param=schema,
            max_retries=3,
            is_chat=is_chat,
        )

        try:
            return response_model.model_validate_json(first_res.text)
        except ValidationError as first_err:
            logger.warning(
                "structured_output_validation_failed_attempting_correction",
                task=task,
                error=str(first_err),
            )

            # Retry once with validation error appended
            correction_prompt = (
                f"{prompt}\n\n[VALIDATION ERROR IN PREVIOUS ATTEMPT]:\n"
                f"{first_err}\n\n"
                "Please return strictly valid JSON correcting the validation errors above."
            )

            retry_res = await self.generate(
                prompt=correction_prompt,
                task=f"{task}_correction",
                prompt_version=prompt_version,
                model=model,
                system=system,
                temperature=temperature,
                seed=seed,
                timeout=timeout,
                format_param=schema,
                max_retries=1,
                is_chat=is_chat,
            )

            try:
                return response_model.model_validate_json(retry_res.text)
            except ValidationError as final_err:
                # Fail closed: never let malformed or unvalidated output reach business logic
                logger.error(
                    "structured_output_failed_closed",
                    task=task,
                    raw_text=retry_res.text,
                    error=str(final_err),
                )
                raise LLMValidationError(
                    message=f"LLM structured output failed validation after retry for task '{task}'. Failing closed.",
                    raw_text=retry_res.text,
                    errors=final_err.errors(),
                ) from final_err

    async def generate_from_template(
        self,
        template_path: str | Path,
        template_vars: Mapping[str, Any],
        task: str,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        timeout: float | None = None,
        is_chat: bool = False,
    ) -> LLMResult:
        """Render prompt from a .jinja file with mandatory version header and execute generate."""
        rendered = load_and_render_prompt(template_path, **template_vars)
        return await self.generate(
            prompt=rendered.text,
            task=task,
            prompt_version=rendered.version,
            model=model,
            system=system,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            is_chat=is_chat,
        )

    async def structured_output_from_template(
        self,
        template_path: str | Path,
        template_vars: Mapping[str, Any],
        response_model: type[T],
        task: str,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        timeout: float | None = None,
        is_chat: bool = False,
    ) -> T:
        """Render prompt from a .jinja file and execute structured output (fail-closed)."""
        rendered = load_and_render_prompt(template_path, **template_vars)
        return await self.structured_output(
            prompt=rendered.text,
            response_model=response_model,
            task=task,
            prompt_version=rendered.version,
            model=model,
            system=system,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            is_chat=is_chat,
        )


_client_instance: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return singleton LLMClient."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
