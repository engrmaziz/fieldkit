"""Client-side A/B experiment config caching and deterministic variant router."""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx
from fieldkit_common.logging import get_logger
from fieldkit_common.settings import get_common_settings

logger = get_logger("fieldkit.llm.experiments")

# In-memory config cache: experiment_name -> (expires_at_timestamp, variants_list)
_CONFIG_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 60.0


def clear_experiment_cache() -> None:
    """Clear cached experiment configs (primarily for testing)."""
    _CONFIG_CACHE.clear()


def assign_variant_by_hash(
    user_id: str,
    experiment_name: str,
    variants: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministically assign a user to an experiment variant using MD5 modulo 100."""
    if not variants:
        return {"name": "default", "model": "qwen2.5:7b", "prompt_version": "1.0.0"}

    digest = hashlib.md5(f"{user_id}:{experiment_name}".encode()).hexdigest()
    bucket = int(digest, 16) % 100

    cumulative = 0
    for variant in variants:
        cumulative += int(variant.get("pct", 0))
        if bucket < cumulative:
            return variant

    return variants[0]


async def resolve_experiment_variant(
    experiment_name: str,
    user_id: str,
    default_model: str = "qwen2.5:7b",
    default_prompt_version: str = "1.0.0",
    tracehub_url: str | None = None,
    timeout: float = 1.0,
) -> tuple[str, str, str]:
    """Resolve model and prompt version for a user within an online A/B experiment.

    Fetches the experiment config from Tracehub with a 60-second in-memory TTL.
    If Tracehub is offline, unreachable, or returns an error, gracefully falls back
    to the provided default model and prompt version without blocking execution.

    Returns:
        (variant_name, model, prompt_version)
    """
    now = time.time()
    cached = _CONFIG_CACHE.get(experiment_name)

    if cached and now < cached[0]:
        variants = cached[1]
    else:
        settings = get_common_settings()
        base_url = (tracehub_url or settings.tracehub_url).rstrip("/")
        endpoint = f"{base_url}/experiments/{experiment_name}/config"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "active")
                    if status == "active":
                        variants = data.get("variants", [])
                        _CONFIG_CACHE[experiment_name] = (now + CACHE_TTL_SECONDS, variants)
                    else:
                        # Paused or completed experiment
                        variants = data.get("variants", [])[:1]
                else:
                    logger.warning(
                        "experiment_fetch_failed_http",
                        experiment=experiment_name,
                        status_code=resp.status_code,
                    )
                    variants = cached[1] if cached else []
        except Exception as exc:
            logger.debug(
                "experiment_fetch_offline_fallback",
                experiment=experiment_name,
                error=str(exc),
            )
            variants = cached[1] if cached else []

    if not variants:
        return ("control", default_model, default_prompt_version)

    assigned = assign_variant_by_hash(user_id=user_id, experiment_name=experiment_name, variants=variants)
    return (
        str(assigned.get("name", "control")),
        str(assigned.get("model", default_model)),
        str(assigned.get("prompt_version", default_prompt_version)),
    )
