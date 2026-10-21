"""Tests for Project 6 (InspectAI) evaluation regression gate and baseline comparisons."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class P6GateVerdict(BaseModel):
    passed: bool
    regressions: list[str]
    deltas: dict[str, float]
    summary_rows: list[dict[str, str | float]]


def evaluate_p6_regression_gate(
    current: dict[str, float],
    baseline: dict[str, float],
    max_drop: float = 0.02,
) -> P6GateVerdict:
    """Compare current InspectAI run metrics against baseline and enforce regression gate."""
    regressions: list[str] = []
    deltas: dict[str, float] = {}
    summary_rows: list[dict[str, str | float]] = []

    # Zero-tolerance metrics: defect escapes must strictly be 0
    zero_tolerance_metrics = {"zero_tolerance_escape_count", "defect_escape_rate"}

    # Lower-is-better metrics (where increase is a regression)
    lower_is_better = {
        "anomaly_p95_latency_ms",
        "defect_calibration_ece",
        "defect_escape_rate",
        "review_queue_rate",
        "edge_service_p95_latency_ms",
        "baseline_score_psi",
        "zero_tolerance_escape_count",
    }

    for key, base_val in baseline.items():
        curr_val = current.get(key, 0.0)
        delta = round(curr_val - base_val, 4)
        deltas[key] = delta

        is_regressed = False
        if key in zero_tolerance_metrics:
            if curr_val > 0:
                is_regressed = True
                regressions.append(f"{key}: {curr_val} > 0 (Zero-tolerance escape violation in automotive parts)")
        elif key in lower_is_better:
            # For latency / queue budget / calibration error, increase > 20% is regression
            if curr_val > base_val * 1.20 and curr_val > 0.05:
                is_regressed = True
                regressions.append(
                    f"{key}: increased from {base_val} to {curr_val} (>20% degradation)"
                )
        else:
            # Higher-is-better metrics (AUROC, F1, Agreement, Throughput)
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
    return P6GateVerdict(
        passed=passed,
        regressions=regressions,
        deltas=deltas,
        summary_rows=summary_rows,
    )


def test_baseline_json_exists_and_valid() -> None:
    """Verify that evals/p6/baseline.json is valid and covers all flagship targets."""
    baseline_path = Path("evals/p6/baseline.json")
    assert baseline_path.exists(), "evals/p6/baseline.json must exist"

    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert data["project"] == "p6-inspectai"
    assert "metrics" in data
    assert "targets" in data

    metrics = data["metrics"]
    targets = data["targets"]

    assert metrics["mvtec_mean_image_auroc"] >= targets["mvtec_mean_image_auroc"]
    assert metrics["mvtec_mean_pixel_auroc"] >= targets["mvtec_mean_pixel_auroc"]
    assert metrics["neu_classifier_macro_f1"] >= targets["neu_classifier_macro_f1"]
    assert metrics["defect_escape_rate"] == 0.0000
    assert metrics["zero_tolerance_escape_count"] == 0
    assert metrics["conveyor_throughput_fps"] >= targets["conveyor_throughput_fps"]
    assert metrics["edge_service_p95_latency_ms"] < targets["edge_service_p95_latency_ms"]


def test_regression_gate_passes_on_identical() -> None:
    """Verify regression gate passes when current metrics match baseline."""
    baseline_path = Path("evals/p6/baseline.json")
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = data["metrics"]

    verdict = evaluate_p6_regression_gate(current=baseline, baseline=baseline)
    assert verdict.passed is True
    assert len(verdict.regressions) == 0


def test_regression_gate_blocks_zero_tolerance_escapes() -> None:
    """Verify regression gate strictly fails if any defective escape is introduced."""
    baseline_path = Path("evals/p6/baseline.json")
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = dict(data["metrics"])

    # Simulate 1 customer escape
    current["zero_tolerance_escape_count"] = 1
    current["defect_escape_rate"] = 0.01

    verdict = evaluate_p6_regression_gate(current=current, baseline=data["metrics"])
    assert verdict.passed is False
    assert any("Zero-tolerance escape violation" in r for r in verdict.regressions)


def test_regression_gate_blocks_on_excessive_drop() -> None:
    """Verify regression gate fails if Macro-F1 or AUROC drops beyond tolerance."""
    baseline_path = Path("evals/p6/baseline.json")
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = dict(data["metrics"])

    # Drop classifier Macro-F1 from 1.0000 to 0.9400 (-6%, exceeds 2% max drop)
    current["neu_classifier_macro_f1"] = 0.9400

    verdict = evaluate_p6_regression_gate(current=current, baseline=data["metrics"], max_drop=0.02)
    assert verdict.passed is False
    assert any("neu_classifier_macro_f1: dropped by" in r for r in verdict.regressions)


def test_regression_gate_passes_within_allowed_tolerance() -> None:
    """Verify regression gate passes when small fluctuation is within 2% margin."""
    baseline_path = Path("evals/p6/baseline.json")
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = dict(data["metrics"])

    # Small 1% drop in pixel AUROC
    current["mvtec_mean_pixel_auroc"] = round(current["mvtec_mean_pixel_auroc"] - 0.01, 4)

    verdict = evaluate_p6_regression_gate(current=current, baseline=data["metrics"], max_drop=0.02)
    assert verdict.passed is True
