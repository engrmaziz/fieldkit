"""API router for trace search, waterfall trees, and operational metrics."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from fieldkit_tracehub.schemas import (
    MetricSeriesResponse,
    TraceListResponse,
    TraceTreeResponse,
)
from fieldkit_tracehub.storage import storage

router = APIRouter(prefix="", tags=["Traces & Metrics"])


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    service: str | None = Query(None, description="Filter by service name"),
    task: str | None = Query(None, description="Filter by task name"),
    model: str | None = Query(None, description="Filter by model name"),
    status: str | None = Query(None, description="Filter by status (OK, ERROR)"),
    min_ms: float | None = Query(None, description="Filter by minimum duration in ms"),
    from_time: datetime | None = Query(None, description="Start time UTC"),
    to_time: datetime | None = Query(None, description="End time UTC"),
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=500, description="Page size limit"),
) -> TraceListResponse:
    """Search and filter execution traces across all Fieldkit AI services."""
    return await storage.search_traces(
        service=service,
        task=task,
        model=model,
        status=status,
        min_ms=min_ms,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        cursor=cursor,
    )


@router.get("/traces/{trace_id}", response_model=TraceTreeResponse)
async def get_trace(trace_id: str) -> TraceTreeResponse:
    """Retrieve full span hierarchy and waterfall timing for a single trace."""
    tree = await storage.get_trace_tree(trace_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Trace with ID '{trace_id}' not found.")
    return tree


@router.get("/metrics", response_model=MetricSeriesResponse)
async def get_metrics(
    series: str = Query("latency_p95", description="Metric series: latency_p50, latency_p95, error_rate, tokens_per_min"),
    service: str | None = Query(None, description="Filter by service"),
    task: str | None = Query(None, description="Filter by task"),
    model: str | None = Query(None, description="Filter by model"),
    from_time: datetime | None = Query(None, description="Start time UTC"),
    to_time: datetime | None = Query(None, description="End time UTC"),
    step: str = Query("1m", description="Rollup step interval"),
) -> MetricSeriesResponse:
    """Query time-series aggregated metrics from ClickHouse metrics_1m table."""
    return await storage.get_metrics(
        series=series,
        service=service,
        task=task,
        model=model,
        from_time=from_time,
        to_time=to_time,
        step=step,
    )
