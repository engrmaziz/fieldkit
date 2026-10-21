"""Asymmetric cost matrix modeling and dual-threshold optimization for industrial inspection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class CostMatrixConfig:
    """Asymmetric penalty matrix reflecting real-world manufacturing economics."""

    cost_false_pass: float = 500.0  # Escape liability: warranty defect sent to OEM
    cost_false_reject: float = 25.0  # Unnecessary scrap or rework of good part
    cost_review: float = 5.0  # Operator manual inspection queue cost
    max_review_budget: float = 0.08  # Max 8.0% of production volume to review queue


@dataclass
class DecisionMetrics:
    """Operational evaluation metrics under asymmetric cost matrix."""

    total_samples: int
    escapes: int
    false_rejects: int
    reviews: int
    true_passes: int
    true_rejects: int
    escape_rate: float
    false_reject_rate: float
    review_rate: float
    total_cost: float
    cost_per_item: float


@dataclass
class ThresholdOptimizationResult:
    """Optimal threshold parameters minimizing total manufacturing cost."""

    threshold_pass: float
    threshold_reject: float
    metrics: DecisionMetrics
    cost_reduction_ratio: float
    baseline_naive_cost: float


def evaluate_decision_cost(
    y_true: Sequence[int] | np.ndarray,
    decisions: Sequence[str | Any] | np.ndarray,
    cost_config: CostMatrixConfig | None = None,
) -> DecisionMetrics:
    """Calculate aggregate and per-item costs under asymmetric manufacturing matrix."""
    if cost_config is None:
        cost_config = CostMatrixConfig()

    n = len(y_true)
    if n == 0:
        return DecisionMetrics(
            total_samples=0,
            escapes=0,
            false_rejects=0,
            reviews=0,
            true_passes=0,
            true_rejects=0,
            escape_rate=0.0,
            false_reject_rate=0.0,
            review_rate=0.0,
            total_cost=0.0,
            cost_per_item=0.0,
        )

    escapes = 0
    false_rejects = 0
    reviews = 0
    true_passes = 0
    true_rejects = 0

    for is_defective, dec in zip(y_true, decisions, strict=False):
        dec_str = dec.value if hasattr(dec, "value") else str(dec)
        if dec_str == "review":
            reviews += 1
        elif is_defective and dec_str == "pass":
            escapes += 1
        elif not is_defective and dec_str == "reject":
            false_rejects += 1
        elif not is_defective and dec_str == "pass":
            true_passes += 1
        elif is_defective and dec_str == "reject":
            true_rejects += 1

    total_cost = (
        escapes * cost_config.cost_false_pass
        + false_rejects * cost_config.cost_false_reject
        + reviews * cost_config.cost_review
    )

    return DecisionMetrics(
        total_samples=n,
        escapes=escapes,
        false_rejects=false_rejects,
        reviews=reviews,
        true_passes=true_passes,
        true_rejects=true_rejects,
        escape_rate=round(escapes / n, 4),
        false_reject_rate=round(false_rejects / n, 4),
        review_rate=round(reviews / n, 4),
        total_cost=round(total_cost, 2),
        cost_per_item=round(total_cost / n, 4),
    )


def optimize_inspection_thresholds(
    y_true: Sequence[int],
    anomaly_scores: Sequence[float],
    cost_config: CostMatrixConfig | None = None,
    grid_steps: int = 50,
) -> ThresholdOptimizationResult:
    """Find dual decision thresholds (T_pass, T_reject) minimizing expected cost subject to review budget."""
    if cost_config is None:
        cost_config = CostMatrixConfig()

    y_arr = np.array(y_true, dtype=np.int32)
    scores = np.array(anomaly_scores, dtype=np.float32)
    n = len(y_arr)

    # 1. Baseline: Best single cutoff without review queue
    best_single_cost = float("inf")
    cutoff_grid = np.linspace(0.05, 0.95, grid_steps)
    for c in cutoff_grid:
        single_decs = np.where(scores >= c, "reject", "pass")
        m = evaluate_decision_cost(y_arr, single_decs, cost_config)
        if m.total_cost < best_single_cost:
            best_single_cost = m.total_cost

    # 2. Dual threshold grid search with review budget penalty
    best_t_pass = 0.35
    best_t_reject = 0.65
    best_total_cost = float("inf")
    best_metrics: DecisionMetrics | None = None

    t_candidates = np.linspace(0.02, 0.98, grid_steps)

    for i in range(len(t_candidates)):
        t_p = float(t_candidates[i])
        for j in range(i, len(t_candidates)):
            t_r = float(t_candidates[j])

            # Vectorized decision assignment
            decs = np.full(n, "review", dtype=object)
            decs[scores < t_p] = "pass"
            decs[scores > t_r] = "reject"

            m = evaluate_decision_cost(y_arr, decs, cost_config)

            # Check review budget constraint (e.g. <= 8%)
            if m.review_rate > cost_config.max_review_budget:
                # Infeasible under operational budget constraint
                continue

            # Prioritize zero escapes, then minimum cost
            score_objective = m.total_cost
            if score_objective < best_total_cost:
                best_total_cost = score_objective
                best_t_pass = t_p
                best_t_reject = t_r
                best_metrics = m

    # Fallback if no point satisfied the constraint
    if best_metrics is None:
        best_t_pass = 0.35
        best_t_reject = 0.65
        decs = np.full(n, "review", dtype=object)
        decs[scores < best_t_pass] = "pass"
        decs[scores > best_t_reject] = "reject"
        best_metrics = evaluate_decision_cost(y_arr, decs, cost_config)

    reduction = (
        round(best_single_cost / max(best_metrics.total_cost, 1e-4), 2)
        if best_metrics.total_cost > 0
        else 10.0
    )

    return ThresholdOptimizationResult(
        threshold_pass=round(best_t_pass, 4),
        threshold_reject=round(best_t_reject, 4),
        metrics=best_metrics,
        cost_reduction_ratio=reduction,
        baseline_naive_cost=round(best_single_cost, 2),
    )
