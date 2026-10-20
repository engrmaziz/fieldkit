"""Emerging Issue Clustering Engine for Fieldkit Ops Copilot (P3 Milestone 5).

Discovers latent problem clusters from customer support tickets, tracks volume growth rates,
and emits automated anomaly incident alerts to Project 7 Tracehub upon detecting defect spikes.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fieldkit_common.logging import get_logger
from pydantic import BaseModel
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

logger = get_logger("fieldkit.copilot.clustering")

PART_NUMBER_REGEX = re.compile(r"\b[A-Z]{2,4}-[0-9]{3,5}\b")


class TicketDocument(BaseModel):
    """Document representation of a support ticket for topic clustering."""

    ticket_id: str
    text: str
    timestamp: datetime
    queue: str = "general_inquiry"
    part_number: str | None = None


class ClusterResult(BaseModel):
    """Extracted topic cluster with defect growth statistics."""

    cluster_id: int
    topic_title: str
    top_terms: list[str]
    part_numbers: list[str]
    current_count: int
    baseline_count: int
    growth_rate: float
    sample_ticket_ids: list[str]


class EmergingIssueEngine:
    """Clustering and defect spike detector for customer support operations."""

    def __init__(
        self,
        spike_growth_threshold: float = 1.5,
        min_spike_volume: int = 5,
        min_cluster_size: int = 2,
        window_days: int = 7,
    ) -> None:
        self.spike_growth_threshold = spike_growth_threshold
        self.min_spike_volume = min_spike_volume
        self.min_cluster_size = min_cluster_size
        self.window_days = window_days

    def cluster_tickets(
        self,
        tickets: list[TicketDocument],
        n_clusters: int = 3,
    ) -> list[ClusterResult]:
        """Group tickets into semantic clusters and compute growth metrics."""
        if not tickets:
            return []

        now = datetime.now(UTC)
        cutoff = now - timedelta(days=self.window_days)

        texts = [t.text for t in tickets]
        k = min(n_clusters, len(tickets))
        if k < 1:
            k = 1

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=500,
            token_pattern=r"(?u)\b[\w-]{2,}\b",
            lowercase=True,
        )
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=5)
            labels = kmeans.fit_predict(tfidf_matrix)
        except Exception as exc:
            logger.warning("Clustering fallback to single cluster", error=str(exc))
            labels = [0] * len(tickets)
            feature_names = []

        clusters: list[ClusterResult] = []

        for cid in range(k):
            cluster_indices = [idx for idx, label in enumerate(labels) if label == cid]
            if len(cluster_indices) < self.min_cluster_size:
                continue

            cluster_tickets = [tickets[i] for i in cluster_indices]

            # 1. Extract Top Terms
            top_terms: list[str] = []
            if len(feature_names) > 0 and hasattr(kmeans, "cluster_centers_"):
                center = kmeans.cluster_centers_[cid]
                top_indices = center.argsort()[::-1][:5]
                top_terms = [str(feature_names[i]) for i in top_indices if center[i] > 0]

            # 2. Extract Associated Part Numbers
            part_numbers: set[str] = set()
            for t in cluster_tickets:
                if t.part_number:
                    part_numbers.add(t.part_number.upper())
                for m in PART_NUMBER_REGEX.finditer(t.text):
                    part_numbers.add(m.group().upper())

            # 3. Compute Current vs Baseline Velocity
            current_count = sum(1 for t in cluster_tickets if t.timestamp >= cutoff)
            baseline_count = sum(1 for t in cluster_tickets if t.timestamp < cutoff)

            growth_rate = 0.0
            if baseline_count > 0:
                growth_rate = round((current_count - baseline_count) / baseline_count, 2)
            elif current_count > 0:
                growth_rate = float(current_count)

            topic_title = " / ".join(top_terms[:3]).title() if top_terms else f"Cluster {cid}"

            clusters.append(
                ClusterResult(
                    cluster_id=cid,
                    topic_title=topic_title,
                    top_terms=top_terms,
                    part_numbers=sorted(part_numbers),
                    current_count=current_count,
                    baseline_count=baseline_count,
                    growth_rate=growth_rate,
                    sample_ticket_ids=[t.ticket_id for t in cluster_tickets[:5]],
                )
            )

        return clusters

    def detect_spikes(self, clusters: list[ClusterResult]) -> list[ClusterResult]:
        """Filter clusters exhibiting growth rate spikes exceeding operational threshold."""
        return [
            c
            for c in clusters
            if c.growth_rate >= self.spike_growth_threshold
            and c.current_count >= self.min_spike_volume
        ]

    def build_tracehub_alert(self, cluster: ClusterResult) -> dict[str, Any]:
        """Construct Tracehub AlertCreate payload."""
        terms_label = ", ".join(cluster.top_terms[:3]) if cluster.top_terms else "defects"
        parts_label = f" on {', '.join(cluster.part_numbers)}" if cluster.part_numbers else ""
        percentage = int(cluster.growth_rate * 100)

        message = (
            f"Emerging defect spike detected: +{percentage}% ticket surge in '{terms_label}'{parts_label} "
            f"({cluster.current_count} tickets vs {cluster.baseline_count} baseline)."
        )

        severity = (
            "critical" if cluster.growth_rate >= 3.0 or cluster.current_count >= 15 else "warning"
        )

        slug = re.sub(r"[^a-z0-9]+", "-", terms_label.lower()).strip("-")
        series = f"copilot:cluster:{slug or 'defect'}"

        return {
            "source": "copilot-clustering",
            "service": "copilot-api",
            "series": series,
            "message": message,
            "severity": severity,
            "details": {
                "cluster_id": cluster.cluster_id,
                "top_terms": cluster.top_terms,
                "part_numbers": cluster.part_numbers,
                "current_count": cluster.current_count,
                "baseline_count": cluster.baseline_count,
                "growth_rate": cluster.growth_rate,
                "sample_ticket_ids": cluster.sample_ticket_ids,
            },
        }

    async def publish_alerts_to_tracehub(
        self,
        spikes: list[ClusterResult],
        tracehub_url: str = "http://localhost:8006",
    ) -> list[dict[str, Any]]:
        """Dispatch detected spikes to Project 7 Tracehub anomaly endpoint."""
        dispatched: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=3.0) as client:
            for spike in spikes:
                payload = self.build_tracehub_alert(spike)
                try:
                    resp = await client.post(f"{tracehub_url.rstrip('/')}/alerts", json=payload)
                    if resp.status_code in (200, 201):
                        dispatched.append(resp.json())
                    else:
                        dispatched.append(payload)
                except Exception as exc:
                    logger.warning(
                        "Tracehub offline, recorded alert locally",
                        error=str(exc),
                        series=payload["series"],
                    )
                    dispatched.append(payload)

        return dispatched
