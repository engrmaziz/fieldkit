"""Synthetic incident injector and benchmark evaluation for Project 7.

Loads 20 ground-truth failure scenarios from evals/p7/incidents.yaml, simulates
telemetry streams, evaluates anomaly detection recall, alert precision, time-to-detect,
and deterministic RCA top-1 dimension accuracy.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml
from fieldkit_tracehub.anomaly.detectors import StreamingAnomalyEngine
from fieldkit_tracehub.anomaly.rca import root_cause_analyzer


def load_incidents(yaml_path: Path) -> list[dict[str, Any]]:
    """Load the labeled incident benchmark from YAML."""
    if not yaml_path.exists():
        raise FileNotFoundError(f"Incident benchmark not found at {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return data.get("incidents", [])


def run_incident_benchmark(yaml_path: Path) -> dict[str, Any]:
    """Execute the 20 incident simulations and report benchmark metrics."""
    incidents = load_incidents(yaml_path)
    print(f"[INFO] Loaded {len(incidents)} labeled incidents from {yaml_path.name}")

    engine = StreamingAnomalyEngine(warmup_points=3)

    detected_count = 0
    total_incidents = len(incidents)
    detection_times_min: list[float] = []
    rca_correct_count = 0
    hallucination_violations = 0

    # Also test 10 clean baseline windows to test false positives
    clean_false_positives = 0
    clean_test_windows = 10

    for i in range(clean_test_windows):
        s_clean = f"service-clean:task_ok:qwen_{i}"
        for _ in range(6):
            anoms = engine.ingest_metric(
                series=s_clean,
                latency_p95=210.0 + (i * 2.0),
                error_count=0,
                total_count=100,
            )
            if anoms:
                clean_false_positives += 1
                break

    print("\n--- Executing Incident Injections ---")
    for inc in incidents:
        inc_id = inc["id"]
        name = inc["name"]
        series = inc["series"]
        metric = inc["metric"]
        b_val = float(inc["baseline_value"])
        a_val = float(inc["anomalous_value"])
        true_dim = inc["true_root_cause_dimension"]
        true_val = inc["true_root_cause_value"]

        # 1. Warm-up series with 4 baseline points
        for _ in range(4):
            engine.ingest_metric(
                series=series,
                latency_p95=b_val,
                error_count=int(b_val * 100) if metric == "error_rate" else 1,
                total_count=100,
            )

        # 2. Inject anomalous window points (simulate up to 5 consecutive minutes)
        is_detected = False
        detected_at_minute = 0.0

        for minute in range(1, 6):
            errs = int(a_val * 100) if metric == "error_rate" else 1
            anoms = engine.ingest_metric(
                series=series,
                latency_p95=a_val,
                error_count=errs,
                total_count=100,
            )
            if anoms:
                is_detected = True
                detected_at_minute = float(minute)
                break

        if is_detected:
            detected_count += 1
            detection_times_min.append(detected_at_minute)
        else:
            detection_times_min.append(10.0)

        # 3. Deterministic RCA attribution test:
        # Create realistic baseline and anomalous distribution where true_dim=true_val is the primary driver
        baseline_samples: list[dict[str, Any]] = []
        anomalous_samples: list[dict[str, Any]] = []

        dims_default = {
            "prompt_version": "1.0.0",
            "model": "qwen2.5:7b",
            "route": "standard_route",
            "plant": "DE-STR",
            "host": "halden-node-01",
            "task": "assistant_rag_qa",
        }

        base_dims = dict(dims_default)
        if base_dims.get(true_dim) == true_val:
            base_dims[true_dim] = f"{true_val}-normal"

        # Baseline: normal latency across all dimensions
        for _ in range(20):
            sample = dict(base_dims)
            sample["value"] = b_val
            sample["trace_id"] = "trc-base-01"
            baseline_samples.append(sample)

        # Anomalous window: 70% of traffic has the anomalous true_dim value and high latency,
        # while 30% background traffic remains on the baseline
        for _ in range(14):
            sample = dict(base_dims)
            sample[true_dim] = true_val
            sample["value"] = a_val
            sample["trace_id"] = f"trc-{inc_id}-anom"
            anomalous_samples.append(sample)

        for _ in range(6):
            sample = dict(base_dims)
            sample["value"] = b_val
            sample["trace_id"] = f"trc-{inc_id}-norm"
            anomalous_samples.append(sample)

        rca_res = root_cause_analyzer.compute_attribution(
            series=series,
            metric=metric,
            baseline_samples=baseline_samples,
            anomalous_samples=anomalous_samples,
        )

        top_attrib_dim = rca_res.top_dimensions[0].dimension if rca_res.top_dimensions else "none"
        if top_attrib_dim == true_dim:
            rca_correct_count += 1

        if rca_res.dropped_hallucinations_count > 0:
            hallucination_violations += rca_res.dropped_hallucinations_count

        status_str = "[DETECTED]" if is_detected else "[MISSED]"
        rca_str = f"RCA={top_attrib_dim} ({'PASS' if top_attrib_dim == true_dim else 'FAIL'})"
        print(f"  {inc_id}: {name[:40]:<40} {status_str} @ {detected_at_minute}m | {rca_str}")

    # Compute aggregate metrics
    recall = detected_count / max(1, total_incidents)
    total_alerts = detected_count + clean_false_positives
    precision = detected_count / max(1, total_alerts)
    median_ttd = statistics.median(detection_times_min) if detection_times_min else 0.0
    rca_accuracy = rca_correct_count / max(1, total_incidents)

    results = {
        "total_incidents": total_incidents,
        "detected_count": detected_count,
        "clean_false_positives": clean_false_positives,
        "recall": recall,
        "precision": precision,
        "median_ttd_minutes": median_ttd,
        "rca_accuracy": rca_accuracy,
        "hallucinations_in_output": hallucination_violations,
    }

    print("\n=======================================================")
    print("   PROJECT 7 ANOMALY & RCA BENCHMARK RESULTS")
    print("=======================================================")
    print(f"  Detection Recall:           {recall * 100:.1f}%  (Target: >= 90.0%) -> {'PASS' if recall >= 0.9 else 'FAIL'}")
    print(f"  Alert Precision:            {precision * 100:.1f}%  (Target: >= 80.0%) -> {'PASS' if precision >= 0.8 else 'FAIL'}")
    print(f"  Median Time to Detect:      {median_ttd:.1f} min  (Target: < 5.0 min) -> {'PASS' if median_ttd < 5.0 else 'FAIL'}")
    print(f"  RCA Top-1 Accuracy:         {rca_accuracy * 100:.1f}%  (Target: >= 70.0%) -> {'PASS' if rca_accuracy >= 0.7 else 'FAIL'}")
    print(f"  Hallucinated Numbers in RCA: {hallucination_violations}         (Target: Strictly 0) -> {'PASS' if hallucination_violations == 0 else 'FAIL'}")
    print("=======================================================\n")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic Incident Injector for Project 7")
    parser.add_argument(
        "--incidents",
        default="evals/p7/incidents.yaml",
        help="Path to labeled incidents YAML (default: evals/p7/incidents.yaml)",
    )
    args = parser.parse_args()

    yaml_path = Path(args.incidents).resolve()
    results = run_incident_benchmark(yaml_path)

    success = (
        results["recall"] >= 0.90
        and results["precision"] >= 0.80
        and results["median_ttd_minutes"] < 5.0
        and results["rca_accuracy"] >= 0.70
        and results["hallucinations_in_output"] == 0
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
