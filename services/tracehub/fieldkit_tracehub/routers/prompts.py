"""API router for Prompt Registry and template version diffing."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from fieldkit_tracehub.prompt_registry import prompt_registry
from fieldkit_tracehub.schemas import (
    PromptCreate,
    PromptRecord,
    PromptSummary,
    PromptVersionDiff,
)

router = APIRouter(prefix="/prompts", tags=["Prompt Registry"])


@router.post("", response_model=PromptRecord)
async def register_prompt(payload: PromptCreate) -> PromptRecord:
    """Register or publish a versioned prompt template."""
    return prompt_registry.register_prompt(payload)


@router.get("", response_model=list[PromptSummary])
async def list_prompts() -> list[PromptSummary]:
    """List all registered prompt templates and their available versions."""
    return prompt_registry.list_prompts()


@router.get("/{name}", response_model=PromptRecord)
async def get_prompt(
    name: str,
    version: str | None = Query(None, description="Specific version (e.g. 1.0.0). Defaults to latest."),
) -> PromptRecord:
    """Retrieve template and metadata for a specific prompt version."""
    rec = prompt_registry.get_prompt(name, version=version)
    if not rec:
        ver_str = f" v{version}" if version else ""
        raise HTTPException(status_code=404, detail=f"Prompt '{name}'{ver_str} not found.")
    return rec


@router.get("/{name}/diff", response_model=PromptVersionDiff)
async def diff_prompt(
    name: str,
    v1: str = Query(..., description="Baseline version (e.g. 1.0.0)"),
    v2: str = Query(..., description="Target version (e.g. 2.0.0)"),
) -> PromptVersionDiff:
    """Compute unified line-by-line diff between two prompt versions."""
    diff = prompt_registry.diff_prompt(name, v1=v1, v2=v2)
    if not diff:
        raise HTTPException(status_code=404, detail=f"Could not compute diff for '{name}' between v{v1} and v{v2}.")
    return diff
