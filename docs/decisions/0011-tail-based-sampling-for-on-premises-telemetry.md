# ADR 0011: Tail-Based Sampling Strategy for Resource-Constrained On-Premises Telemetry

- **Status**: Accepted
- **Date**: 2026-10-20
- **Author**: engrmaziz

## Context
In on-premises and edge deployments across Halden Industrie's manufacturing plants (Hamburg `DE-HAM`, Stuttgart `DE-STR`, Wrocław `PL-WRO`), machines have bounded disk storage and network bandwidth. Capturing 100% of all trace spans from high-throughput microservices (vision pipelines generating 60 FPS events, batch document OCR, continuous RAG queries) would rapidly exhaust disk quotas within days.

Conversely, aggressive head-based sampling (e.g. sampling 10% of requests at the start of a transaction) inevitably drops rare, catastrophic error traces, intermittent timeouts, and anomalous P99 latency spikes because the final outcome of the trace is unknown when the sampling decision is made.

## Decision
We implement a **tail-based sampling pipeline** in the OpenTelemetry Collector (`deploy/otel/collector.yaml`) utilizing the `tail_sampling` processor in the OpenTelemetry Collector Contrib image:

```yaml
processors:
  tail_sampling:
    decision_wait: 5s
    num_traces: 10000
    expected_new_traces_per_sec: 2000
    policies:
      # Policy 1: Always retain 100% of error traces
      - name: drop-no-errors
        type: status_code
        status_code: { status_codes: [ ERROR ] }
      # Policy 2: Always retain 100% of slow traces (> 5 seconds)
      - name: slow-traces
        type: numeric_attribute
        numeric_attribute: { key: duration_ms, min_value: 5000 }
      # Policy 3: Keep 20% probabilistic sample of normal baseline traces
      - name: probabilistic-sample
        type: probabilistic
        probabilistic: { sampling_percentage: 20.0 }
```

### Architectural Principles:
1. **Decision Wait Buffer**: Traces are held in a bounded memory buffer for 5 seconds to assemble all child spans before evaluating sampling policies.
2. **Guaranteed Failure Retention**: 100% of spans carrying `status.code == ERROR` or HTTP 5xx responses are retained for post-mortem root-cause analysis.
3. **P99 Outlier Capture**: 100% of slow operations exceeding 5,000 ms duration are preserved regardless of service origin.
4. **Statistical Baseline**: 20% of healthy baseline traces are retained to maintain accurate statistical background distributions for anomaly detectors and latency quantiles.

## Alternatives Rejected
- **Head-Based Sampling (SDK Level)**:
  - Discarding 80% of traces at the client library before execution means 80% of production errors and intermittent crashes are permanently lost.
- **100% Full Retention**:
  - Overwhelms disk storage on single-node edge deployments, triggering emergency disk truncation and IO starvation.
- **Dynamic Adaptive Rate Limiting**:
  - Adds non-deterministic sampling biases and substantial stateful synchronization overhead across distributed workers.

## Consequences
- **Positive**:
  - Guarantees 100% capture of all production failures, exceptions, and extreme latency outliers.
  - Reduces sustained storage throughput and ClickHouse disk consumption by $\approx 76\%$.
  - Preserves representative distributions for P50/P90/P95 latency quantile tracking.
- **Negative**:
  - Requires running the OpenTelemetry Collector Contrib distribution (`otel/opentelemetry-collector-contrib`) which uses $\approx 150\text{ MB}$ of memory for the trace buffering window.
  - Spans delayed by more than the 5-second `decision_wait` window risk being evaluated on incomplete trace segments.
