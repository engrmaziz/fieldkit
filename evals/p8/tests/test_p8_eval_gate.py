"""Tests for Project 8 evaluation regression gate and baseline comparisons."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class P8GateVerdict(BaseModel):
    passed: bool
    regressions: list[str]
    deltas: dict[str, float]
    summary_rows: list[dict[str, str | float]]


def evaluate_p8_regression_gate(
    current: dict[str, float],
    baseline: dict[str, float],
    targets: dict[str, float],
) -> P8GateVerdict:
    """Compare current Project 8 metrics against golden baseline and targets."""
    regressions: list[str] = []
    deltas: dict[str, float] = {}
    summary_rows: list[dict[str, str | float]] = []

    # Zero-tolerance metrics: must strictly be 0
    zero_tolerance_metrics = {
        "chaos_duplicate_downstream_side_effects",
        "chaos_stuck_tasks_expired_leases",
        "disaster_recovery_rpo_loss_records",
        "helm_lint_failure_count",
    }

    # Lower-is-better metrics (where increase > threshold is a regression)
    lower_is_better = {
        "disaster_recovery_rto_seconds",
        "upgrade_under_traffic_error_rate_pct",
        "chaos_duplicate_downstream_side_effects",
        "chaos_stuck_tasks_expired_leases",
        "disaster_recovery_rpo_loss_records",
        "helm_lint_failure_count",
    }

    for key, base_val in baseline.items():
        curr_val = current.get(key, 0.0)
        target_val = targets.get(key, base_val)
        delta = round(curr_val - base_val, 4)
        deltas[key] = delta

        is_regressed = False
        if key in zero_tolerance_metrics:
            if curr_val > 0:
                is_regressed = True
                regressions.append(
                    f"{key}: {curr_val} > 0 (Zero-tolerance industrial violation)"
                )
        elif key in lower_is_better:
            if curr_val > target_val:
                is_regressed = True
                regressions.append(
                    f"{key}: {curr_val} exceeded SLA target of {target_val}"
                )
        else:
            # Higher-is-better metrics (throughput, completion rate, data preservation)
            if curr_val < target_val:
                is_regressed = True
                regressions.append(
                    f"{key}: {curr_val} dropped below SLA target of {target_val}"
                )

        summary_rows.append(
            {
                "metric": key,
                "current": curr_val,
                "baseline": base_val,
                "target": target_val,
                "status": "REGRESSION" if is_regressed else "PASS",
            }
        )

    return P8GateVerdict(
        passed=len(regressions) == 0,
        regressions=regressions,
        deltas=deltas,
        summary_rows=summary_rows,
    )


def test_p8_baseline_json_schema_and_integrity() -> None:
    """Verify that evals/p8/baseline.json conforms to schema and has valid non-negative metrics."""
    baseline_path = ROOT_DIR / "evals" / "p8" / "baseline.json"
    assert baseline_path.exists(), "evals/p8/baseline.json must exist"

    with open(baseline_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["project"] == "p8-deploy-workflow"
    assert "metrics" in data
    assert "targets" in data

    metrics = data["metrics"]
    targets = data["targets"]

    for k in [
        "chaos_workflow_completion_rate_pct",
        "chaos_duplicate_downstream_side_effects",
        "chaos_stuck_tasks_expired_leases",
        "event_replay_state_determinism_pct",
        "workflow_engine_throughput_steps_per_sec",
        "disaster_recovery_rto_seconds",
        "disaster_recovery_rpo_loss_records",
        "upgrade_under_traffic_error_rate_pct",
        "failed_upgrade_rollback_data_preservation_pct",
        "helm_lint_failure_count",
    ]:
        assert k in metrics, f"Missing metric {k}"
        assert k in targets, f"Missing target {k}"
        assert metrics[k] >= 0, f"Metric {k} must be non-negative"


def test_p8_regression_gate_passes_on_current_baseline() -> None:
    """Verify that current baseline passes regression gate with zero regressions."""
    baseline_path = ROOT_DIR / "evals" / "p8" / "baseline.json"
    with open(baseline_path, encoding="utf-8") as f:
        data = json.load(f)

    verdict = evaluate_p8_regression_gate(
        current=data["metrics"],
        baseline=data["metrics"],
        targets=data["targets"],
    )

    assert verdict.passed is True
    assert len(verdict.regressions) == 0


def test_p8_regression_gate_detects_zero_tolerance_violation() -> None:
    """Verify gate fails-closed if duplicate side effects or data loss is injected."""
    baseline_path = ROOT_DIR / "evals" / "p8" / "baseline.json"
    with open(baseline_path, encoding="utf-8") as f:
        data = json.load(f)

    # Injected duplicate side effect violation
    corrupted_metrics = dict(data["metrics"])
    corrupted_metrics["chaos_duplicate_downstream_side_effects"] = 1.0

    verdict = evaluate_p8_regression_gate(
        current=corrupted_metrics,
        baseline=data["metrics"],
        targets=data["targets"],
    )

    assert verdict.passed is False
    assert any("Zero-tolerance" in r for r in verdict.regressions)


def test_p8_regression_gate_detects_throughput_degradation() -> None:
    """Verify gate fails if workflow engine throughput drops below 50 steps/s target."""
    baseline_path = ROOT_DIR / "evals" / "p8" / "baseline.json"
    with open(baseline_path, encoding="utf-8") as f:
        data = json.load(f)

    degraded_metrics = dict(data["metrics"])
    degraded_metrics["workflow_engine_throughput_steps_per_sec"] = 24.5

    verdict = evaluate_p8_regression_gate(
        current=degraded_metrics,
        baseline=data["metrics"],
        targets=data["targets"],
    )

    assert verdict.passed is False
    assert any("workflow_engine_throughput_steps_per_sec" in r for r in verdict.regressions)


def test_p8_regression_gate_detects_rto_sla_violation() -> None:
    """Verify gate fails if disaster recovery RTO exceeds the 60.0s SLA target."""
    baseline_path = ROOT_DIR / "evals" / "p8" / "baseline.json"
    with open(baseline_path, encoding="utf-8") as f:
        data = json.load(f)

    slow_rto_metrics = dict(data["metrics"])
    slow_rto_metrics["disaster_recovery_rto_seconds"] = 78.4

    verdict = evaluate_p8_regression_gate(
        current=slow_rto_metrics,
        baseline=data["metrics"],
        targets=data["targets"],
    )

    assert verdict.passed is False
    assert any("disaster_recovery_rto_seconds" in r for r in verdict.regressions)
