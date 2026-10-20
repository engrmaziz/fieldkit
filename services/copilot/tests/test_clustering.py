"""Unit tests for Emerging Issue Clustering Engine (Project 3 Milestone 5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fieldkit_copilot.clustering import (
    EmergingIssueEngine,
    TicketDocument,
)


@pytest.fixture
def sample_ticket_corpus() -> list[TicketDocument]:
    """Generate representative industrial support tickets with an emerging HX-400 leak spike."""
    now = datetime.now(UTC)
    tickets: list[TicketDocument] = []

    # 1. Baseline tickets (8 days ago)
    for i in range(10):
        tickets.append(
            TicketDocument(
                ticket_id=f"TICK-OLD-{i}",
                text="Liefertermin für Standarddichtungen verzögert. Wann kommt das Paket?",
                timestamp=now - timedelta(days=8),
                queue="order_delivery",
            )
        )

    # 2. Stable baseline tickets for HX-400 (only 2 in previous window)
    for i in range(2):
        tickets.append(
            TicketDocument(
                ticket_id=f"TICK-BASE-{i}",
                text="Hydraulikventil HX-400 leckt minimal am Flansch.",
                timestamp=now - timedelta(days=9),
                queue="returns_rma",
                part_number="HX-400",
            )
        )

    # 3. Recent spike of HX-400 seal leak defect tickets (12 in current window -> +500% spike)
    for i in range(12):
        tickets.append(
            TicketDocument(
                ticket_id=f"TICK-SPIKE-{i}",
                text=f"Ventil HX-400 zeigt starken Druckverlust und Ölaustritt an Dichtung {i}. Defekt!",
                timestamp=now - timedelta(days=2),
                queue="returns_rma",
                part_number="HX-400",
            )
        )

    return tickets


def test_clustering_extracts_topics(sample_ticket_corpus: list[TicketDocument]) -> None:
    engine = EmergingIssueEngine(min_cluster_size=2)
    clusters = engine.cluster_tickets(sample_ticket_corpus, n_clusters=2)

    assert len(clusters) >= 2
    # Check that HX-400 / ventil cluster was discovered
    hx_clusters = [
        c
        for c in clusters
        if "hx-400" in [t.lower() for t in c.top_terms]
        or "hx-400" in [p.lower() for p in c.part_numbers]
    ]
    assert len(hx_clusters) >= 1
    assert any(
        "ventil" in [t.lower() for t in c.top_terms] or "hx-400" in [t.lower() for t in c.top_terms]
        for c in hx_clusters
    )


def test_spike_detection_and_alert_generation(sample_ticket_corpus: list[TicketDocument]) -> None:
    engine = EmergingIssueEngine(spike_growth_threshold=1.5, min_spike_volume=5)
    clusters = engine.cluster_tickets(sample_ticket_corpus, n_clusters=2)

    spikes = engine.detect_spikes(clusters)
    assert len(spikes) >= 1

    hx_spike = next(
        s
        for s in spikes
        if "HX-400" in s.part_numbers or "hx-400" in [t.lower() for t in s.top_terms]
    )
    assert hx_spike.growth_rate >= 1.5
    assert hx_spike.current_count >= 5

    # Generate Tracehub alert payload
    alert_payload = engine.build_tracehub_alert(hx_spike)
    assert alert_payload["source"] == "copilot-clustering"
    assert (
        "HX-400" in alert_payload["message"]
        or "ventil" in alert_payload["message"].lower()
        or "druckverlust" in alert_payload["message"].lower()
    )
    assert alert_payload["severity"] in ("warning", "critical")
    assert alert_payload["details"]["current_count"] == hx_spike.current_count
