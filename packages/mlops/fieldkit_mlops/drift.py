"""Population Stability Index (PSI) distribution drift calculation and monitoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

logger = logging.getLogger("fieldkit.mlops.drift")


@dataclass
class DriftAnalysisResult:
    """Evaluation result of population distribution drift analysis."""

    product_id: str
    psi: float
    status: str  # "STABLE", "WARNING", "CRITICAL"
    reference_count: int
    actual_count: int
    drift_detected: bool
    bin_edges: list[float] = field(default_factory=list)
    expected_pcts: list[float] = field(default_factory=list)
    actual_pcts: list[float] = field(default_factory=list)
    alert_message: str | None = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def calculate_psi(
    reference: np.ndarray | list[float],
    actual: np.ndarray | list[float],
    num_bins: int = 5,
    epsilon: float = 1e-4,
) -> float:
    """Calculate Population Stability Index (PSI) between reference and actual distributions.

    PSI Formula:
        PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))

    Thresholds:
        PSI < 0.10: Stable, no significant shift.
        0.10 <= PSI <= 0.20: Moderate shift, warning to inspect incoming batches.
        PSI > 0.20: Significant distribution drift, triggers P7 alerting / retrain gate.
    """
    ref_arr = np.asarray(reference, dtype=np.float64)
    act_arr = np.asarray(actual, dtype=np.float64)

    if len(ref_arr) == 0 or len(act_arr) == 0:
        return 0.0

    # Determine adaptive bin count for statistical reliability (at least 5 samples per bin)
    k = min(num_bins, max(2, len(act_arr) // 8))
    quantiles = np.linspace(0.0, 1.0, k + 1)
    bin_edges = np.quantile(ref_arr, quantiles)

    # Ensure strictly monotonic increasing bin edges
    for i in range(1, len(bin_edges)):
        if bin_edges[i] <= bin_edges[i - 1]:
            bin_edges[i] = bin_edges[i - 1] + 1e-5

    # Expand boundaries to catch all edge samples
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    # Bin counts
    ref_counts, _ = np.histogram(ref_arr, bins=bin_edges)
    act_counts, _ = np.histogram(act_arr, bins=bin_edges)

    # Convert to proportions using Laplace smoothing to prevent zero-bin infinities
    ref_pct = (ref_counts + 1.0) / (len(ref_arr) + k)
    act_pct = (act_counts + 1.0) / (len(act_arr) + k)

    # PSI calculation
    psi_value = np.sum((act_pct - ref_pct) * np.log(act_pct / ref_pct))
    return float(max(0.0, psi_value))


class ScoreDriftMonitor:
    """Monitors incoming model scores against reference baseline and alerts on drift."""

    def __init__(self, critical_threshold: float = 0.20, warning_threshold: float = 0.10) -> None:
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold
        self._reference_scores: dict[str, np.ndarray] = {}
        self._live_scores: dict[str, list[float]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}

    def set_reference_scores(self, product_id: str, scores: list[float] | np.ndarray) -> None:
        """Set baseline reference score distribution (e.g. from validated training week)."""
        self._reference_scores[product_id] = np.asarray(scores, dtype=np.float64)
        if product_id not in self._live_scores:
            self._live_scores[product_id] = []
        if product_id not in self._history:
            self._history[product_id] = []

    def record_score(self, product_id: str, score: float) -> None:
        """Record a live inspection score for drift tracking."""
        if product_id not in self._live_scores:
            self._live_scores[product_id] = []
        self._live_scores[product_id].append(float(score))

    def analyze_drift(self, product_id: str, min_samples: int = 15) -> DriftAnalysisResult:
        """Compute PSI of recent live score distribution vs reference baseline."""
        ref = self._reference_scores.get(product_id)
        live = self._live_scores.get(product_id, [])

        if ref is None or len(ref) == 0:
            return DriftAnalysisResult(
                product_id=product_id,
                psi=0.0,
                status="NO_REFERENCE",
                reference_count=0,
                actual_count=len(live),
                drift_detected=False,
                alert_message="No reference baseline established for product",
            )

        if len(live) < min_samples:
            return DriftAnalysisResult(
                product_id=product_id,
                psi=0.0,
                status="INSUFFICIENT_SAMPLES",
                reference_count=len(ref),
                actual_count=len(live),
                drift_detected=False,
                alert_message=f"Need >= {min_samples} samples, currently {len(live)}",
            )

        psi = calculate_psi(ref, live)

        if psi > self.critical_threshold:
            status = "CRITICAL"
            drift_detected = True
            alert_message = (
                f"CRITICAL distribution drift detected for {product_id}: PSI={psi:.4f} > "
                f"{self.critical_threshold:.2f}. New material supplier or tooling wear likely."
            )
        elif psi >= self.warning_threshold:
            status = "WARNING"
            drift_detected = False
            alert_message = f"Moderate distribution shift for {product_id}: PSI={psi:.4f}."
        else:
            status = "STABLE"
            drift_detected = False
            alert_message = None

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "psi": round(psi, 4),
            "status": status,
            "sample_count": len(live),
        }
        self._history.setdefault(product_id, []).append(record)

        return DriftAnalysisResult(
            product_id=product_id,
            psi=round(psi, 4),
            status=status,
            reference_count=len(ref),
            actual_count=len(live),
            drift_detected=drift_detected,
            alert_message=alert_message,
        )

    def get_history(self, product_id: str) -> list[dict[str, Any]]:
        """Return history of drift evaluations."""
        return self._history.get(product_id, [])
