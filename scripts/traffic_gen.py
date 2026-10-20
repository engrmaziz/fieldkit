"""High-performance synthetic traffic and telemetry replay generator for Project 7 (Tracehub).

Generates realistic OpenTelemetry spans across all Fieldkit services (P1 through P6),
replaying query distributions, token profiles, latency quantiles, and plant allocations.
Supports both rate-limited continuous replay and ultra-fast generation mode for scale benchmarks.
"""

from __future__ import annotations

import argparse
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

# Sample queries from Halden Industrie workloads
HALDEN_QUERIES = [
    ("assistant_rag_qa", "assistant-api", "Welche Sicherheitsanforderungen gelten fuer hydraulische Steuerungsbloecke nach DIN EN ISO 4413?"),
    ("assistant_rag_qa", "assistant-api", "What are the metallurgical tolerance limits for cylinder wall casing in Plant DE-HAM?"),
    ("assistant_sql_query", "assistant-api", "SELECT supplier_name, count(*) FROM purchase_orders WHERE plant='DE-HAM' GROUP BY 1"),
    ("assistant_sql_query", "assistant-api", "Top 5 suppliers by defective hydraulic valves in Q3 2026"),
    ("foundry_er_resolve", "foundry-api", "Resolve vendor record 'Mueller Hydr. Bauteile GmbH' against GLEIF Golden Copy"),
    ("foundry_drift_profile", "foundry-api", "Profile schema fingerprints on planning_de_ham.xlsx for missing headers"),
    ("copilot_ticket_triage", "copilot-api", "Stoerung am Hydraulikaggregat Pumpenstation 3 Druckabfall"),
    ("copilot_routing", "copilot-api", "Support ticket #4812: leaking seal on valve block assembly line 2"),
    ("doc_extract_clauses", "doc-intel", "Extract indemnity and warranty clauses from Parker Hannifin supply contract"),
    ("defect_retrain_eval", "defect-inspect", "Evaluate patchcore anomaly detection on milled surface roughness Ra 0.8"),
    ("video_ppe_check", "video-analytics", "Zone violation detection on CCTV feed cam-ham-04 welding bay"),
]

SERVICES = [
    "assistant-api",
    "foundry-api",
    "copilot-api",
    "doc-intel",
    "defect-inspect",
    "video-analytics",
]

MODELS = ["qwen2.5:7b", "qwen2.5-coder:7b", "nomic-embed-text"]
PROMPT_VERSIONS = ["1.0.0", "1.1.0", "2.0.0"]
PLANTS = ["DE-HAM", "DE-STR", "PL-WRO"]


def generate_traffic_span(index: int, seed_offset: int = 0) -> dict[str, Any]:
    """Generate a single structured telemetry span with GenAI semconv."""
    task, default_svc, prompt_text = random.choice(HALDEN_QUERIES)
    service = default_svc if random.random() < 0.8 else random.choice(SERVICES)
    model = random.choice(MODELS)
    prompt_version = random.choice(PROMPT_VERSIONS)
    plant = random.choice(PLANTS)

    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    parent_span_id = uuid.uuid4().hex[:16] if (index % 3 != 0) else ""

    is_error = random.random() < 0.015
    status = "ERROR" if is_error else "OK"

    # Lognormal latency with realistic enterprise tail
    if is_error:
        duration_ms = round(random.uniform(5000.0, 7500.0), 2)
    else:
        duration_ms = round(random.lognormvariate(4.8, 0.5), 2)

    now = datetime.now(UTC)
    start_time = now.isoformat()

    input_tokens = random.randint(45, 1250)
    output_tokens = random.randint(12, 480) if not is_error else 0
    ttft_ms = round(random.uniform(18.0, 65.0), 2) if not is_error else 0.0

    attributes: dict[str, str] = {
        "gen_ai.system": "ollama",
        "gen_ai.request.model": model,
        "gen_ai.request.temperature": "0.0",
        "gen_ai.usage.input_tokens": str(input_tokens),
        "gen_ai.usage.output_tokens": str(output_tokens),
        "fieldkit.task": task,
        "fieldkit.prompt_version": prompt_version,
        "fieldkit.plant": plant,
        "fieldkit.ttft_ms": str(ttft_ms),
        "fieldkit.prompt_sample": prompt_text[:80],
    }

    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "service": service,
        "name": f"llm.{task}",
        "start_time": start_time,
        "duration_ms": duration_ms,
        "status": status,
        "attributes": attributes,
        "model": model,
        "task": task,
        "prompt_version": prompt_version,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def run_traffic_generation(
    total_spans: int = 1000,
    rate_per_sec: float = 0.0,
    fast_mode: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute synthetic traffic generation and measure throughput."""
    random.seed(seed)
    print("\n=======================================================")
    print("      FIELDKIT P7 TRAFFIC GENERATOR & BENCHMARK        ")
    print(f"      Target: {total_spans:,} spans | Rate: {'Unthrottled (Fast)' if fast_mode or rate_per_sec <= 0 else f'{rate_per_sec} spans/s'} ")
    print("=======================================================\n")

    start_time = time.perf_counter()
    generated_spans: list[dict[str, Any]] = []
    latencies: list[float] = []
    error_count = 0

    interval = 1.0 / rate_per_sec if rate_per_sec > 0 and not fast_mode else 0.0

    for i in range(total_spans):
        step_start = time.perf_counter()
        span = generate_traffic_span(i, seed_offset=seed)
        generated_spans.append(span)
        latencies.append(span["duration_ms"])
        if span["status"] == "ERROR":
            error_count += 1

        if interval > 0:
            elapsed_step = time.perf_counter() - step_start
            sleep_time = interval - elapsed_step
            if sleep_time > 0:
                time.sleep(sleep_time)

        if (i + 1) % max(1, (total_spans // 5)) == 0 or i == total_spans - 1:
            progress_pct = ((i + 1) / total_spans) * 100
            elapsed = time.perf_counter() - start_time
            current_rate = (i + 1) / max(elapsed, 0.001)
            print(f"  [{progress_pct:5.1f}%] {i + 1:,}/{total_spans:,} spans generated ({current_rate:,.0f} spans/s)")

    total_time = max(time.perf_counter() - start_time, 0.0001)
    throughput = total_spans / total_time

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    summary = {
        "total_spans": total_spans,
        "elapsed_seconds": round(total_time, 4),
        "throughput_spans_per_sec": round(throughput, 1),
        "error_count": error_count,
        "error_rate_pct": round((error_count / total_spans) * 100, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "target_met": throughput >= 5000.0 if fast_mode else True,
    }

    print("\n--- Summary Metrics ---")
    print(f"  - Total Spans:      {summary['total_spans']:,}")
    print(f"  - Generation Time:  {summary['elapsed_seconds']:.4f} s")
    print(f"  - Throughput:       {summary['throughput_spans_per_sec']:,} spans/s (Target: >= 5,000 spans/s)")
    print(f"  - Error Rate:       {summary['error_rate_pct']:.2f}%")
    print(f"  - Latency P50:      {summary['latency_p50_ms']} ms")
    print(f"  - Latency P95:      {summary['latency_p95_ms']} ms (Target: < 500 ms)")
    print(f"  - Latency P99:      {summary['latency_p99_ms']} ms")
    print("-----------------------\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fieldkit P7 synthetic traffic generator")
    parser.add_argument("--spans", type=int, default=1000, help="Number of spans to generate")
    parser.add_argument("--rate", type=float, default=0.0, help="Spans per second rate limit (0 for unthrottled)")
    parser.add_argument("--fast", action="store_true", help="Run unthrottled high-throughput benchmark mode")
    parser.add_argument("--seed", type=int, default=42, help="Random number generator seed")
    args = parser.parse_args()

    run_traffic_generation(
        total_spans=args.spans,
        rate_per_sec=args.rate,
        fast_mode=args.fast or (args.rate <= 0),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
