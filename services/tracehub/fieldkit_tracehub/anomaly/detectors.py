"""Streaming statistical anomaly detectors for time-series telemetry.

Implements:
1. Robust Z-Score: median/MAD over rolling 24h window; triggers when |z| > 4.0 for 3 consecutive minutes.
2. EWMA Variance Band: Exponentially weighted moving average with dynamic variance bands.
3. CUSUM: Cumulative Sum control charts for persistent gradual shifts on p95 latency and output tokens.
4. Error-Rate Burst Rule: Triggers when error rate > 5% and error count >= 10 in a 1-minute window.
"""

from __future__ import annotations

import math
from typing import Any

from fieldkit_common.logging import get_logger

logger = get_logger("tracehub.anomaly.detectors")


class RobustZScoreDetector:
    """Robust Z-Score detector using Median Absolute Deviation (MAD).

    Formula:
        MAD = median(|x_i - median(X)|)
        Modified z = 0.6745 * (x - median(X)) / MAD
    """

    def __init__(
        self,
        z_threshold: float = 4.0,
        consecutive_points: int = 3,
        window_size: int = 1440,
        min_history: int = 5,
    ) -> None:
        self.z_threshold = z_threshold
        self.consecutive_points = consecutive_points
        self.window_size = window_size
        self.min_history = min_history
        self._history: list[float] = []
        self._consecutive_breaches: int = 0

    def observe(self, value: float) -> tuple[bool, float, float]:
        """Observe a value and evaluate for anomaly.

        Returns: (is_anomaly, current_z_score, estimated_threshold)
        """
        self._history.append(value)
        if len(self._history) > self.window_size:
            self._history.pop(0)

        if len(self._history) < self.min_history:
            return (False, 0.0, self.z_threshold)

        sorted_vals = sorted(self._history)
        n = len(sorted_vals)
        median_val = sorted_vals[n // 2]

        deviations = [abs(x - median_val) for x in sorted_vals]
        deviations.sort()
        mad_val = deviations[n // 2]

        if mad_val < 1e-6:
            # Handle near-zero variance gracefully
            z_score = 0.0 if abs(value - median_val) < 1e-6 else 5.0
        else:
            z_score = (0.6745 * (value - median_val)) / mad_val

        if abs(z_score) >= self.z_threshold:
            self._consecutive_breaches += 1
        else:
            self._consecutive_breaches = 0

        is_anomaly = self._consecutive_breaches >= self.consecutive_points
        return (is_anomaly, round(z_score, 2), self.z_threshold)


class EWMABandDetector:
    """Exponentially Weighted Moving Average (EWMA) detector with dynamic variance bounds."""

    def __init__(
        self,
        alpha: float = 0.2,
        band_multiplier: float = 3.0,
        min_history: int = 5,
    ) -> None:
        self.alpha = alpha
        self.band_multiplier = band_multiplier
        self.min_history = min_history
        self._mean: float | None = None
        self._variance: float | None = None
        self._count: int = 0

    def observe(self, value: float) -> tuple[bool, float, float]:
        """Observe value and check if it falls outside the EWMA variance band.

        Returns: (is_anomaly, current_value, band_upper_limit)
        """
        self._count += 1
        if self._mean is None:
            self._mean = value
            self._variance = 0.0
            return (False, value, value)

        # Check anomaly against prior distribution bounds before updating state
        prior_mean = self._mean
        prior_var = self._variance or 0.0
        prior_std = math.sqrt(max(0.05 * (abs(prior_mean) + 1.0), prior_var))
        upper_bound = prior_mean + (self.band_multiplier * prior_std)
        lower_bound = max(0.0, prior_mean - (self.band_multiplier * prior_std))

        is_anomaly = (self._count >= self.min_history) and (value > upper_bound or value < lower_bound)

        # Update EWMA mean and variance for next observations
        diff = value - self._mean
        self._mean = self.alpha * value + (1.0 - self.alpha) * self._mean
        if self._variance is None:
            self._variance = diff ** 2
        else:
            self._variance = self.alpha * (diff ** 2) + (1.0 - self.alpha) * self._variance

        return (is_anomaly, round(value, 2), round(upper_bound, 2))


class CUSUMDetector:
    """Cumulative Sum (CUSUM) detector for persistent gradual shifts."""

    def __init__(
        self,
        slack_k: float = 0.5,
        threshold_h: float = 5.0,
        min_history: int = 5,
    ) -> None:
        self.slack_k = slack_k
        self.threshold_h = threshold_h
        self.min_history = min_history
        self._baseline_mean: float | None = None
        self._baseline_std: float | None = None
        self._history: list[float] = []
        self._s_pos: float = 0.0
        self._s_neg: float = 0.0

    def observe(self, value: float) -> tuple[bool, float, float]:
        """Observe value and compute CUSUM cumulative deviations.

        Returns: (is_anomaly, max_cusum_statistic, threshold_h)
        """
        self._history.append(value)
        if len(self._history) < self.min_history:
            return (False, 0.0, self.threshold_h)

        if self._baseline_mean is None or self._baseline_std is None:
            self._baseline_mean = sum(self._history) / len(self._history)
            variance = sum((x - self._baseline_mean) ** 2 for x in self._history) / len(self._history)
            self._baseline_std = math.sqrt(max(0.01, variance))

        std_dev = max(0.01, self._baseline_std)
        z = (value - self._baseline_mean) / std_dev

        # Cumulative positive and negative deviation tracking
        self._s_pos = max(0.0, self._s_pos + z - self.slack_k)
        self._s_neg = max(0.0, self._s_neg - z - self.slack_k)

        statistic = max(self._s_pos, self._s_neg)
        is_anomaly = statistic >= self.threshold_h
        if is_anomaly:
            # Partial reset to prevent permanent trigger state
            self._s_pos = self.threshold_h * 0.5
            self._s_neg = self.threshold_h * 0.5

        return (is_anomaly, round(statistic, 2), self.threshold_h)


class ErrorRateBurstDetector:
    """Rule-based burst detector for error rate spikes."""

    def __init__(
        self,
        min_error_rate: float = 0.05,
        min_error_count: int = 10,
    ) -> None:
        self.min_error_rate = min_error_rate
        self.min_error_count = min_error_count

    def observe(self, error_count: int, total_count: int) -> tuple[bool, float, float]:
        """Evaluate if errors form a statistically critical burst.

        Returns: (is_burst, observed_error_rate, threshold_rate)
        """
        if total_count <= 0:
            return (False, 0.0, self.min_error_rate)

        rate = error_count / total_count
        is_burst = (rate >= self.min_error_rate) and (error_count >= self.min_error_count)
        return (is_burst, round(rate, 4), self.min_error_rate)


class AnomalyEvent:
    """Detected anomaly incident metadata."""

    def __init__(
        self,
        series: str,
        detector: str,
        metric: str,
        current_value: float,
        threshold: float,
        severity: str = "critical",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.series = series
        self.detector = detector
        self.metric = metric
        self.current_value = current_value
        self.threshold = threshold
        self.severity = severity
        self.details = details or {}


class StreamingAnomalyEngine:
    """Manages detector pipelines across series with warm-up periods."""

    def __init__(self, warmup_points: int = 3) -> None:
        self.warmup_points = warmup_points
        # series -> detector_name -> instance
        self._detectors: dict[str, dict[str, Any]] = {}
        self._observations_count: dict[str, int] = {}

    def _get_or_create_detectors(self, series: str) -> dict[str, Any]:
        if series not in self._detectors:
            self._detectors[series] = {
                "robust_z": RobustZScoreDetector(),
                "ewma": EWMABandDetector(),
                "cusum": CUSUMDetector(),
                "error_burst": ErrorRateBurstDetector(),
            }
            self._observations_count[series] = 0
        return self._detectors[series]

    def ingest_metric(
        self,
        series: str,
        latency_p95: float,
        error_count: int = 0,
        total_count: int = 100,
    ) -> list[AnomalyEvent]:
        """Ingest a 1-minute rollup point and evaluate active detectors."""
        detectors = self._get_or_create_detectors(series)
        self._observations_count[series] += 1
        count = self._observations_count[series]

        anomalies: list[AnomalyEvent] = []

        # 1. Error-rate burst detector (evaluated even during early warmup for safety)
        burst_det: ErrorRateBurstDetector = detectors["error_burst"]
        is_burst, rate, thresh_rate = burst_det.observe(error_count, total_count)
        if is_burst:
            anomalies.append(
                AnomalyEvent(
                    series=series,
                    detector="error_burst",
                    metric="error_rate",
                    current_value=rate,
                    threshold=thresh_rate,
                    severity="critical",
                    details={"error_count": error_count, "total_count": total_count},
                )
            )

        # 2. Warm-up gate for statistical detectors
        if count <= self.warmup_points:
            detectors["robust_z"].observe(latency_p95)
            detectors["ewma"].observe(latency_p95)
            detectors["cusum"].observe(latency_p95)
            return anomalies

        # 3. Robust Z-Score
        z_det: RobustZScoreDetector = detectors["robust_z"]
        is_z, z_score, z_thresh = z_det.observe(latency_p95)
        if is_z:
            anomalies.append(
                AnomalyEvent(
                    series=series,
                    detector="robust_z",
                    metric="latency_p95",
                    current_value=latency_p95,
                    threshold=z_thresh,
                    severity="critical",
                    details={"z_score": z_score},
                )
            )

        # 4. CUSUM persistent shift detector
        cusum_det: CUSUMDetector = detectors["cusum"]
        is_cusum, stat, cusum_thresh = cusum_det.observe(latency_p95)
        if is_cusum:
            anomalies.append(
                AnomalyEvent(
                    series=series,
                    detector="cusum",
                    metric="latency_p95",
                    current_value=latency_p95,
                    threshold=cusum_thresh,
                    severity="warning",
                    details={"cusum_statistic": stat},
                )
            )

        return anomalies
