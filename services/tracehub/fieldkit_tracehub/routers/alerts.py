"""FastAPI router for anomaly incidents, root-cause analysis, and alerting."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from fieldkit_tracehub.anomaly.alerting import alert_manager
from fieldkit_tracehub.anomaly.detectors import StreamingAnomalyEngine
from fieldkit_tracehub.anomaly.rca import root_cause_analyzer
from fieldkit_tracehub.schemas import (
    AlertCreate,
    AlertListResponse,
    AnomalyAlert,
)

router = APIRouter(prefix="/alerts", tags=["Anomaly Detection & Alerting"])
scan_engine = StreamingAnomalyEngine()


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status: str | None = Query(None, description="Filter by status ('active', 'resolved')"),
) -> AlertListResponse:
    """List operational anomaly alerts with RCA summaries and notification statuses."""
    alerts = alert_manager.list_alerts(status=status)
    active_count = sum(1 for a in alert_manager.list_alerts() if a.status == "active")
    resolved_count = sum(1 for a in alert_manager.list_alerts() if a.status == "resolved")
    return AlertListResponse(
        alerts=alerts,
        total_active=active_count,
        total_resolved=resolved_count,
    )


@router.get("/{alert_id}", response_model=AnomalyAlert)
async def get_alert(alert_id: str) -> AnomalyAlert:
    """Retrieve full detail, RCA dimension breakdown, and example traces for an incident."""
    alert = alert_manager.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@router.post("", response_model=AnomalyAlert)
async def ingest_external_alert(payload: AlertCreate) -> AnomalyAlert:
    """Accept external alerts from Vision Health, Copilot Insights, or Inspection Drift."""
    return alert_manager.ingest_external_alert(payload)


@router.post("/{alert_id}/resolve", response_model=AnomalyAlert)
async def resolve_alert(alert_id: str) -> AnomalyAlert:
    """Manually resolve an operational incident alert."""
    resolved = alert_manager.resolve_alert(alert_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return resolved


@router.post("/scan/simulate", response_model=list[AnomalyAlert])
async def simulate_anomaly_scan(
    series: str = Query("assistant-api:assistant_rag_qa:qwen2.5:7b"),
    latency_p95: float = Query(2200.0),
    error_count: int = Query(15),
    total_count: int = Query(100),
) -> list[AnomalyAlert]:
    """Simulate streaming metric ingestion and run detector algorithms."""
    events = scan_engine.ingest_metric(
        series=series,
        latency_p95=latency_p95,
        error_count=error_count,
        total_count=total_count,
    )

    dispatched_alerts: list[AnomalyAlert] = []
    for ev in events:
        # Compute RCA breakdown
        rca = root_cause_analyzer.compute_attribution(
            series=ev.series,
            metric=ev.metric,
            baseline_samples=[{"prompt_version": "1.0.0", "model": "qwen2.5:7b", "plant": "DE-HAM", "value": 580.0}],
            anomalous_samples=[
                {"prompt_version": "3.0.0-rc1", "model": "qwen2.5:7b", "plant": "DE-HAM", "value": latency_p95, "trace_id": "trc-sim-01"}
            ],
        )

        alt = alert_manager.dispatch_anomaly(
            series=ev.series,
            detector=ev.detector,
            metric=ev.metric,
            current_value=ev.current_value,
            threshold=ev.threshold,
            severity=ev.severity,
            rca=rca,
            details=ev.details,
        )
        if alt:
            dispatched_alerts.append(alt)

    return dispatched_alerts
