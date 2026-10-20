"""Unit tests for synthetic traffic generator and benchmark replay."""

from scripts.traffic_gen import generate_traffic_span, run_traffic_generation


def test_generate_traffic_span_schema() -> None:
    """Verifies that generated synthetic span adheres to OpenTelemetry and GenAI conventions."""
    span = generate_traffic_span(1, seed_offset=42)

    assert "trace_id" in span
    assert len(span["trace_id"]) == 32
    assert "span_id" in span
    assert len(span["span_id"]) == 16
    assert span["name"].startswith("llm.")
    assert span["service"] in [
        "assistant-api",
        "foundry-api",
        "copilot-api",
        "doc-intel",
        "defect-inspect",
        "video-analytics",
    ]
    assert span["status"] in ["OK", "ERROR"]
    assert "attributes" in span
    assert span["attributes"]["gen_ai.system"] == "ollama"
    assert "fieldkit.task" in span["attributes"]
    assert "fieldkit.plant" in span["attributes"]
    assert span["input_tokens"] > 0


def test_run_traffic_generation_summary() -> None:
    """Verifies the batch replay summary and metrics computation."""
    summary = run_traffic_generation(total_spans=100, fast_mode=True, seed=42)

    assert summary["total_spans"] == 100
    assert summary["throughput_spans_per_sec"] > 0
    assert summary["latency_p50_ms"] > 0
    assert summary["latency_p95_ms"] >= summary["latency_p50_ms"]
    assert summary["latency_p99_ms"] >= summary["latency_p95_ms"]
    assert 0.0 <= summary["error_rate_pct"] <= 100.0
