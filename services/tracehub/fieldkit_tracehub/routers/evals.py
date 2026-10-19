"""API router for evaluation benchmark runs and regression comparisons."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from fieldkit_tracehub.eval_engine import eval_engine
from fieldkit_tracehub.schemas import (
    EvalComparisonResponse,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunSummary,
)

router = APIRouter(prefix="/eval-runs", tags=["Evaluation & Regressions"])


@router.post("", response_model=EvalRunDetail)
async def create_eval_run(payload: EvalRunCreate) -> EvalRunDetail:
    """Publish an evaluation benchmark run to Tracehub."""
    return eval_engine.store_eval_run(payload)


@router.get("", response_model=list[EvalRunSummary])
async def list_eval_runs(
    suite: str | None = Query(None, description="Filter by suite name"),
) -> list[EvalRunSummary]:
    """List all stored evaluation runs."""
    return eval_engine.list_eval_runs(suite=suite)


@router.get("/compare", response_model=EvalComparisonResponse)
async def compare_eval_runs(
    baseline_id: str = Query(..., description="Run ID of the baseline evaluation"),
    candidate_id: str = Query(..., description="Run ID of the candidate evaluation"),
) -> EvalComparisonResponse:
    """Compare two evaluation runs item-by-item with 95% bootstrap confidence intervals."""
    comparison = eval_engine.compare_eval_runs(baseline_id=baseline_id, candidate_id=candidate_id)
    if not comparison:
        raise HTTPException(
            status_code=404,
            detail=f"Could not compare runs '{baseline_id}' and '{candidate_id}'. Ensure both exist.",
        )
    return comparison


@router.get("/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: str) -> EvalRunDetail:
    """Retrieve full details and items of a specific evaluation run."""
    run = eval_engine.get_eval_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found.")
    return run
