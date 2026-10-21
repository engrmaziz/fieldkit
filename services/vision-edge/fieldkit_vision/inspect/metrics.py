"""Prometheus telemetry gauges, counters, and histograms for industrial inspection."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

INSPECTION_REQUESTS_TOTAL = Counter(
    "fieldkit_inspection_requests_total",
    "Total manufactured components inspected",
    ["product_id", "disposition"],
)

INSPECTION_LATENCY_SECONDS = Histogram(
    "fieldkit_inspection_latency_seconds",
    "End-to-end edge inspection latency in seconds",
    ["product_id"],
    buckets=(0.005, 0.010, 0.025, 0.050, 0.075, 0.100, 0.250, 0.500),
)

INSPECTION_ANOMALY_SCORE = Gauge(
    "fieldkit_inspection_latest_anomaly_score",
    "Latest normalized anomaly score [0.0, 1.0]",
    ["product_id"],
)

INSPECTION_REVIEW_QUEUE_DEPTH = Gauge(
    "fieldkit_inspection_review_queue_depth",
    "Number of ambiguous component inspections awaiting human review",
    ["product_id"],
)

INSPECTION_ESCAPES_TOTAL = Counter(
    "fieldkit_inspection_escapes_total",
    "Total defect escapes detected post-dispatch",
    ["product_id"],
)
