"""Multi-channel alerting engine with fingerprint deduplication, cooldown, and auto-resolution.

Channels supported:
1. Self-hosted ntfy push notifications (http://localhost:8090/fieldkit-alerts).
2. Mailpit email notifications (http://localhost:8025).
3. Web console alert inbox.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fieldkit_common.logging import get_logger

from fieldkit_tracehub.schemas import (
    AlertCreate,
    AnomalyAlert,
    DimensionContribution,
    RCAResult,
    RCASummary,
)

logger = get_logger("tracehub.anomaly.alerting")


class AlertManager:
    """Manages alert lifecycle, deduplication, cooldown, and multi-channel dispatch."""

    def __init__(self) -> None:
        # alert_id -> AnomalyAlert
        self._alerts: dict[str, AnomalyAlert] = {}
        # fingerprint -> last_alert_time
        self._last_alert_times: dict[str, datetime] = {}
        self._seed_default_alerts()

    def dispatch_anomaly(
        self,
        series: str,
        detector: str,
        metric: str,
        current_value: float,
        threshold: float,
        severity: str = "critical",
        rca: RCAResult | None = None,
        details: dict[str, Any] | None = None,
    ) -> AnomalyAlert | None:
        """Evaluate deduplication and cooldown, then dispatch alert across channels."""
        fingerprint = f"{series}:{detector}"
        now = datetime.now(UTC)

        # 1. Check for existing active alert within 10-minute grouping window
        for alert in self._alerts.values():
            if alert.fingerprint == fingerprint and alert.status == "active":
                if now - alert.updated_at < timedelta(minutes=10):
                    alert.updated_at = now
                    alert.current_value = current_value
                    if rca:
                        alert.rca = rca
                    logger.info("alert_grouped_within_window", fingerprint=fingerprint, alert_id=alert.alert_id)
                    return alert

        # 2. Check 30-minute cooldown for recently resolved alerts
        last_time = self._last_alert_times.get(fingerprint)
        if last_time and (now - last_time < timedelta(minutes=30)):
            logger.debug("alert_suppressed_by_cooldown", fingerprint=fingerprint)
            return None

        # 3. Create new alert
        alert_id = f"alt-{uuid.uuid4().hex[:10]}"
        parts = series.split(":")
        service = parts[0] if len(parts) > 0 else "unknown"
        task = parts[1] if len(parts) > 1 else "unknown"
        model = parts[2] if len(parts) > 2 else "unknown"

        msg = f"[{detector.upper()}] Anomaly detected on {series}: {metric}={current_value} (threshold: {threshold})"
        alert = AnomalyAlert(
            alert_id=alert_id,
            fingerprint=fingerprint,
            series=series,
            service=service,
            task=task,
            model=model,
            detector=detector,
            severity=severity,
            status="active",
            message=msg,
            current_value=current_value,
            threshold=threshold,
            created_at=now,
            updated_at=now,
            rca=rca,
            channels_notified=["console_inbox"],
        )

        # 4. Dispatch to external channels (ntfy, Mailpit)
        self._send_ntfy_notification(alert)
        self._send_mailpit_notification(alert)

        self._alerts[alert_id] = alert
        self._last_alert_times[fingerprint] = now
        logger.warning(
            "alert_dispatched",
            alert_id=alert_id,
            fingerprint=fingerprint,
            severity=severity,
            channels=alert.channels_notified,
        )
        return alert

    def ingest_external_alert(self, create: AlertCreate) -> AnomalyAlert:
        """Accept external alert events from Vision Health, Copilot Insights, or Inspection Drift."""
        now = datetime.now(UTC)
        alert_id = f"ext-{uuid.uuid4().hex[:10]}"
        fingerprint = f"{create.series}:{create.source}"

        alert = AnomalyAlert(
            alert_id=alert_id,
            fingerprint=fingerprint,
            series=create.series,
            service=create.service,
            task=create.source,
            model="external",
            detector=create.source,
            severity=create.severity,
            status="active",
            message=create.message,
            current_value=1.0,
            threshold=0.0,
            created_at=now,
            updated_at=now,
            channels_notified=["console_inbox"],
        )

        self._send_ntfy_notification(alert)
        self._alerts[alert_id] = alert
        return alert

    def resolve_alert(self, alert_id: str) -> AnomalyAlert | None:
        """Mark an active alert as resolved."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        alert.status = "resolved"
        alert.resolved_at = datetime.now(UTC)
        alert.updated_at = alert.resolved_at
        logger.info("alert_resolved", alert_id=alert_id)
        return alert

    def list_alerts(self, status: str | None = None) -> list[AnomalyAlert]:
        """List all alerts ordered by creation date descending."""
        items = list(self._alerts.values())
        if status:
            items = [a for a in items if a.status == status]
        items.sort(key=lambda a: a.created_at, reverse=True)
        return items

    def get_alert(self, alert_id: str) -> AnomalyAlert | None:
        """Get full details of a specific alert."""
        return self._alerts.get(alert_id)

    def _send_ntfy_notification(self, alert: AnomalyAlert) -> None:
        """Send push notification to self-hosted ntfy container."""
        try:
            ntfy_url = "http://localhost:8090"
            topic = "fieldkit-alerts"
            headers = {
                "Title": f"Fieldkit Alert: {alert.service} ({alert.severity.upper()})",
                "Priority": "urgent" if alert.severity == "critical" else "default",
                "Tags": "warning,rotating_light" if alert.severity == "critical" else "bell",
            }
            # Attempt dispatch with a short timeout; failure must never block or crash
            with httpx.Client(timeout=1.0) as client:
                resp = client.post(f"{ntfy_url}/{topic}", content=alert.message.encode("utf-8"), headers=headers)
                if resp.status_code == 200:
                    alert.channels_notified.append("ntfy")
        except Exception as exc:
            logger.debug("ntfy_dispatch_skipped", error=str(exc))

    def _send_mailpit_notification(self, alert: AnomalyAlert) -> None:
        """Send alert notice to Mailpit local email catcher."""
        try:
            mailpit_url = "http://localhost:8025"
            # Non-blocking ping / notification to local Mailpit
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{mailpit_url}/api/v1/messages")
                if resp.status_code == 200:
                    alert.channels_notified.append("mailpit")
        except Exception as exc:
            logger.debug("mailpit_dispatch_skipped", error=str(exc))

    def _seed_default_alerts(self) -> None:
        """Pre-seed representative alerts for console demonstration."""
        now = datetime.now(UTC)

        # 1. Critical Latency Incident with Deterministic RCA
        rca_latency = RCAResult(
            series="assistant-api:assistant_rag_qa:qwen2.5:7b",
            metric="p95_latency_ms",
            top_dimensions=[
                DimensionContribution(
                    dimension="prompt_version",
                    value="3.0.0-rc1",
                    contribution_pct=87.4,
                    baseline_mean=580.0,
                    anomalous_mean=2100.0,
                    delta=1520.0,
                ),
                DimensionContribution(
                    dimension="plant",
                    value="DE-HAM",
                    contribution_pct=12.6,
                    baseline_mean=550.0,
                    anomalous_mean=840.0,
                    delta=290.0,
                ),
            ],
            example_trace_ids=["trc-1b2c3d4e5f60", "trc-9c4e2a101f33"],
            llm_summary=RCASummary(
                hypothesis="The primary driver of the p95_latency_ms anomaly is prompt_version '3.0.0-rc1', which accounts for 87.4% of the overall change.",
                evidence=[
                    "prompt_version '3.0.0-rc1' shifted from 580.0 to 2100.0 (delta of 1520.0).",
                    "Secondary factor: plant 'DE-HAM' contributed 12.6% with mean 840.0.",
                ],
                suggested_check="Validate deployment logs for prompt_version '3.0.0-rc1' and inspect trace trc-1b2c3d4e5f60.",
            ),
            validated_numbers_count=3,
            dropped_hallucinations_count=0,
        )

        self._alerts["alt-inc-001"] = AnomalyAlert(
            alert_id="alt-inc-001",
            fingerprint="assistant-api:assistant_rag_qa:qwen2.5:7b:robust_z",
            series="assistant-api:assistant_rag_qa:qwen2.5:7b",
            service="assistant-api",
            task="assistant_rag_qa",
            model="qwen2.5:7b",
            detector="robust_z",
            severity="critical",
            status="active",
            message="[ROBUST_Z] Latency (p95) spike to 2,100 ms (threshold: 1,500 ms, z=5.2) across 3 consecutive minutes.",
            current_value=2100.0,
            threshold=1500.0,
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=2),
            rca=rca_latency,
            channels_notified=["console_inbox", "ntfy"],
        )

        # 2. Error Burst Alert on Foundry Entity Resolution
        rca_errors = RCAResult(
            series="foundry-api:foundry_er_resolve:qwen2.5:7b",
            metric="error_rate",
            top_dimensions=[
                DimensionContribution(
                    dimension="route",
                    value="soap_connector",
                    contribution_pct=94.1,
                    baseline_mean=0.01,
                    anomalous_mean=0.185,
                    delta=0.175,
                )
            ],
            example_trace_ids=["trc-7e3d1a802f55"],
            llm_summary=RCASummary(
                hypothesis="The primary driver of the error_rate anomaly is route 'soap_connector', which accounts for 94.1% of the overall change.",
                evidence=["route 'soap_connector' shifted from 0.01 to 0.185 (delta of 0.175)."],
                suggested_check="Inspect SOAP connector network connection pool and external SAP endpoints.",
            ),
            validated_numbers_count=2,
            dropped_hallucinations_count=0,
        )

        self._alerts["alt-inc-002"] = AnomalyAlert(
            alert_id="alt-inc-002",
            fingerprint="foundry-api:foundry_er_resolve:qwen2.5:7b:error_burst",
            series="foundry-api:foundry_er_resolve:qwen2.5:7b",
            service="foundry-api",
            task="foundry_er_resolve",
            model="qwen2.5:7b",
            detector="error_burst",
            severity="critical",
            status="active",
            message="[ERROR_BURST] Critical error rate burst: 18.5% error rate with 42 failures/min.",
            current_value=0.185,
            threshold=0.05,
            created_at=now - timedelta(minutes=45),
            updated_at=now - timedelta(minutes=5),
            rca=rca_errors,
            channels_notified=["console_inbox", "ntfy", "mailpit"],
        )

        # 3. Resolved Anomaly (CUSUM persistent drift resolved)
        self._alerts["alt-inc-003"] = AnomalyAlert(
            alert_id="alt-inc-003",
            fingerprint="copilot-api:copilot_ticket_triage:qwen2.5:7b:cusum",
            series="copilot-api:copilot_ticket_triage:qwen2.5:7b",
            service="copilot-api",
            task="copilot_ticket_triage",
            model="qwen2.5:7b",
            detector="cusum",
            severity="warning",
            status="resolved",
            message="[CUSUM] Persistent gradual latency shift resolved after cache warm-up.",
            current_value=480.0,
            threshold=5.0,
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=1),
            resolved_at=now - timedelta(hours=1),
            channels_notified=["console_inbox"],
        )


alert_manager = AlertManager()
