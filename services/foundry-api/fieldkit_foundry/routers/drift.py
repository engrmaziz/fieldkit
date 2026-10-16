"""Drift governance router: query drift events and approve column rename proposals."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fieldkit_common.logging import get_logger
from fieldkit_common.otel import get_tracer
from fieldkit_ingest.drift import DriftStore
from pydantic import BaseModel

logger = get_logger("fieldkit.foundry.drift")
tracer = get_tracer("foundry-api.drift")

router = APIRouter(prefix="/drift", tags=["drift"])


class ApproveRequest(BaseModel):
    approved_by: str = "analyst"


class DriftEventResponse(BaseModel):
    event_id: str
    run_id: str
    source: str
    event_type: str
    severity: str
    column_name: str
    details: dict[str, Any]
    suggestion: dict[str, Any] | None = None
    status: str
    created_at: str


@router.get("/events")
async def list_drift_events(
    source: str | None = Query(None, description="Filter by data source"),
    run_id: str | None = Query(None, description="Filter by ingest run ID"),
    severity: str | None = Query(None, description="Filter by severity: BLOCK, WARN"),
    status: str | None = Query(None, description="Filter by status: open, suggested, approved, rejected"),
) -> list[dict[str, Any]]:
    """List detected schema and statistical drift events with governance status."""
    store = DriftStore()
    events: list[dict[str, Any]] = []

    try:
        # Check DuckDB fallback store or Postgres
        if store.fallback_path.exists():
            import duckdb

            con = duckdb.connect(store.fallback_path.as_posix())
            query = "SELECT event_id, run_id, source, event_type, severity, column_name, details, suggestion, status, created_at FROM drift_event WHERE 1=1"
            params: list[Any] = []
            if source:
                query += " AND source = ?"
                params.append(source)
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if status:
                query += " AND status = ?"
                params.append(status)

            rows = con.execute(query, params).fetchall()
            for r in rows:
                events.append(
                    {
                        "event_id": r[0],
                        "run_id": r[1],
                        "source": r[2],
                        "event_type": r[3],
                        "severity": r[4],
                        "column_name": r[5],
                        "details": json.loads(r[6]) if isinstance(r[6], str) else r[6],
                        "suggestion": json.loads(r[7]) if r[7] and isinstance(r[7], str) else r[7],
                        "status": r[8],
                        "created_at": str(r[9]),
                    }
                )
            con.close()
    except Exception as exc:
        logger.error("error_listing_drift_events", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to retrieve drift events") from exc

    return events


@router.post("/{event_id}/approve")
async def approve_drift_mapping(
    event_id: str,
    payload: ApproveRequest | None = None,
) -> dict[str, Any]:
    """Approve a suggested column rename mapping.

    Stores the mapping into contract_override table so subsequent ingest runs
    automatically substitute the column without mutating git-tracked YAML contracts.
    """
    store = DriftStore()
    approved_by = payload.approved_by if payload else "analyst"

    with tracer.start_as_current_span("drift.approve") as span:
        span.set_attribute("event_id", event_id)
        span.set_attribute("approved_by", approved_by)

        success = store.approve_mapping(event_id=event_id, approved_by=approved_by)
        if not success:
            logger.warning("drift_event_approval_failed", event_id=event_id)
            raise HTTPException(
                status_code=404,
                detail=f"Drift event '{event_id}' not found or has no rename proposal to approve.",
            )

        logger.info("drift_mapping_approved", event_id=event_id, approved_by=approved_by)
        return {
            "status": "approved",
            "event_id": event_id,
            "approved_by": approved_by,
            "message": "Column mapping override successfully registered in contract_override table.",
        }


@router.get("/overrides")
async def list_overrides(source: str = "erp_vendors") -> dict[str, str]:
    """List active column rename overrides for a given source."""
    store = DriftStore()
    return store.get_active_overrides(source=source)
