"""Tests for evaluation regression gate logic and baseline comparison."""

import json
from pathlib import Path

from pydantic import BaseModel


class GateVerdict(BaseModel):
    passed: bool
    regressions: list[str]
    deltas: dict[str, float]
    summary_rows: list[dict[str, str | float]]


def evaluate_regression_gate(
    current: dict[str, float],
    baseline: dict[str, float],
    max_drop: float = 0.02,
) -> GateVerdict:
    """Compare current run metrics against baseline and enforce regression gate."""
    regressions: list[str] = []
    deltas: dict[str, float] = {}
    summary_rows: list[dict[str, str | float]] = []

    # Strict zero-tolerance metrics
    zero_tolerance_metrics = {"acl_leak_count", "sql_unsafe_count"}

    for key, base_val in baseline.items():
        curr_val = current.get(key, 0.0)
        delta = round(curr_val - base_val, 4)
        deltas[key] = delta

        is_regressed = False
        if key in zero_tolerance_metrics:
            if curr_val > 0:
                is_regressed = True
                regressions.append(f"{key}: {curr_val} > 0 (Zero-tolerance security violation)")
        else:
            if delta < -max_drop:
                is_regressed = True
                regressions.append(
                    f"{key}: dropped by {abs(delta):.2%} (exceeds max allowed drop of {max_drop:.2%})"
                )

        summary_rows.append({
            "metric": key,
            "baseline": base_val,
            "current": curr_val,
            "delta": delta,
            "status": "FAIL" if is_regressed else "PASS",
        })

    passed = len(regressions) == 0
    return GateVerdict(
        passed=passed,
        regressions=regressions,
        deltas=deltas,
        summary_rows=summary_rows,
    )


def test_regression_gate_passes_within_tolerance() -> None:
    """Ensure small fluctuations within 2 percentage points pass cleanly."""
    baseline = {
        "retrieval_recall_at_10": 0.9400,
        "routing_accuracy": 0.9600,
        "acl_leak_count": 0.0,
    }
    # Slight drop by 1% (0.01) is within 2% tolerance
    current = {
        "retrieval_recall_at_10": 0.9300,
        "routing_accuracy": 0.9600,
        "acl_leak_count": 0.0,
    }
    verdict = evaluate_regression_gate(current, baseline, max_drop=0.02)
    assert verdict.passed is True
    assert len(verdict.regressions) == 0


def test_regression_gate_fails_on_drop_greater_than_2_percent() -> None:
    """Ensure any metric dropping by more than 2 percentage points triggers failure."""
    baseline = {
        "retrieval_recall_at_10": 0.9400,
        "routing_accuracy": 0.9600,
        "acl_leak_count": 0.0,
    }
    # Drop by 3% (0.03) exceeds 2% tolerance
    current = {
        "retrieval_recall_at_10": 0.9050,
        "routing_accuracy": 0.9600,
        "acl_leak_count": 0.0,
    }
    verdict = evaluate_regression_gate(current, baseline, max_drop=0.02)
    assert verdict.passed is False
    assert len(verdict.regressions) == 1
    assert "retrieval_recall_at_10" in verdict.regressions[0]


def test_regression_gate_fails_on_any_acl_leak() -> None:
    """Ensure any ACL leak instantly fails the gate regardless of other metrics."""
    baseline = {
        "retrieval_recall_at_10": 0.9400,
        "routing_accuracy": 0.9600,
        "acl_leak_count": 0.0,
    }
    # Improved metrics, but 1 ACL leak
    current = {
        "retrieval_recall_at_10": 0.9900,
        "routing_accuracy": 1.0000,
        "acl_leak_count": 1.0,
    }
    verdict = evaluate_regression_gate(current, baseline, max_drop=0.02)
    assert verdict.passed is False
    assert any("acl_leak_count" in r for r in verdict.regressions)


def test_regression_gate_fails_on_unsafe_sql() -> None:
    """Ensure any unsafe SQL execution attempt instantly fails the gate."""
    baseline = {
        "sql_execution_accuracy": 0.8000,
        "sql_unsafe_count": 0.0,
    }
    current = {
        "sql_execution_accuracy": 0.9000,
        "sql_unsafe_count": 1.0,
    }
    verdict = evaluate_regression_gate(current, baseline, max_drop=0.02)
    assert verdict.passed is False
    assert any("sql_unsafe_count" in r for r in verdict.regressions)


def test_baseline_json_structure() -> None:
    """Verify that evals/p2/baseline.json is valid and contains required keys."""
    baseline_file = Path("evals/p2/baseline.json")
    assert baseline_file.exists(), "evals/p2/baseline.json must exist"
    data = json.loads(baseline_file.read_text(encoding="utf-8"))

    assert "metrics" in data
    assert "targets" in data
    assert "max_allowed_drop" in data

    metrics = data["metrics"]
    assert "retrieval_recall_at_10" in metrics
    assert "routing_accuracy" in metrics
    assert "acl_leak_count" in metrics
    assert "sql_ast_validity" in metrics
    assert metrics["acl_leak_count"] == 0
