"""API router for online A/B experiments and variant traffic resolution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from fieldkit_tracehub.experiments import experiment_engine
from fieldkit_tracehub.schemas import (
    ExperimentConfigResponse,
    ExperimentCreate,
    ExperimentRecord,
    ExperimentResolveRequest,
    ExperimentResolveResponse,
    ExperimentResultsResponse,
)

router = APIRouter(prefix="/experiments", tags=["A/B Experiments"])


@router.post("", response_model=ExperimentRecord)
async def create_experiment(payload: ExperimentCreate) -> ExperimentRecord:
    """Register or update an online A/B experiment."""
    return experiment_engine.create_experiment(payload)


@router.get("", response_model=list[ExperimentRecord])
async def list_experiments(
    status: str | None = Query(None, description="Filter by status ('active', 'paused', 'completed')"),
) -> list[ExperimentRecord]:
    """List all registered A/B experiments."""
    return experiment_engine.list_experiments(status=status)


@router.get("/{name}", response_model=ExperimentRecord)
async def get_experiment(name: str) -> ExperimentRecord:
    """Retrieve full details of an A/B experiment."""
    exp = experiment_engine.get_experiment(name)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found.")
    return exp


@router.get("/{name}/config", response_model=ExperimentConfigResponse)
async def get_experiment_config(name: str) -> ExperimentConfigResponse:
    """Fetch lightweight cached experiment config for LLM clients."""
    cfg = experiment_engine.get_experiment_config(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found.")
    return cfg


@router.post("/{name}/resolve", response_model=ExperimentResolveResponse)
async def resolve_experiment_variant(
    name: str,
    payload: ExperimentResolveRequest,
) -> ExperimentResolveResponse:
    """Deterministically assign a user to an experiment variant arm."""
    exp = experiment_engine.get_experiment(name)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found.")

    variant_name, model, prompt_version = experiment_engine.resolve_variant(
        experiment_name=name,
        user_id=payload.user_id,
    )
    return ExperimentResolveResponse(
        experiment_name=name,
        variant_name=variant_name,
        model=model,
        prompt_version=prompt_version,
        user_id=payload.user_id,
    )


@router.get("/{name}/results", response_model=ExperimentResultsResponse)
async def get_experiment_results(name: str) -> ExperimentResultsResponse:
    """Retrieve observed variant performance metrics, statistical deltas, and stop rule status."""
    results = experiment_engine.get_experiment_results(name)
    if not results:
        raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found.")
    return results
