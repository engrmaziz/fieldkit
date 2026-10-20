# ADR 0010: ClickHouse vs PostgreSQL/TimescaleDB for Long-Term Analytical Span Storage

- **Status**: Accepted
- **Date**: 2026-10-20
- **Author**: engrmaziz

## Context
Project 7 builds "Tracehub", a self-hosted, OpenTelemetry-native observability platform capturing distributed traces, token usage, latency quantiles, and span events across all 6 Fieldkit AI services (P1 through P6). Halden Industrie GmbH operates under strict air-gapped constraints:
1. **Zero Cloud Telemetry Egress**: Telemetry cannot be sent to commercial SaaS platforms (Langfuse, Datadog, Honeycomb, Arize).
2. **High Ingestion Throughput**: Generating high-frequency telemetry (RAG queries, document OCR, defect inspection frames) produces thousands of spans per second.
3. **Resource-Constrained Footprint**: The entire platform must operate locally on developer laptops (16GB RAM) or single plant edge nodes without dedicated database clusters.
4. **Analytical Query Speed**: Aggregations across tens of millions of spans (e.g. P95 latency by model and prompt version over 30 days) must complete with $p95 < 500\text{ ms}$.

We evaluated three storage backends:
- **PostgreSQL 16 / TimescaleDB**: Already running in the `core` profile for relational ontology data.
- **ClickHouse**: Dedicated columnar analytical database designed for real-time telemetry.
- **Elasticsearch / OpenSearch**: Traditional document-based log and trace search engine.

## Decision
We select **ClickHouse** as the primary columnar storage engine for distributed spans and minute-level aggregated metrics in the `observe` profile:
1. **Kafka Engine & Materialized Views**: Incoming spans from the OpenTelemetry Collector land on Redpanda topic `otel.spans`. ClickHouse consumes directly via a `Kafka` engine table and flattens them into the `spans` table via a materialized view.
2. **MergeTree Storage with Partitioning & TTL**: Spans are stored in a `MergeTree` table partitioned monthly by `toYYYYMM(start_time)`, ordered by `(service, task, toStartOfMinute(start_time), trace_id)`, with a 30-day retention time-to-live (`TTL start_time + INTERVAL 30 DAY`).
3. **AggregatingMergeTree for Instant Metrics**: A secondary materialized view rolls spans into `metrics_1m` maintaining `quantilesState` (P50, P90, P95, P99), request counts, error counts, and token summaries. Tracehub queries pre-aggregated rollups via `quantilesMerge` in milliseconds.

## Alternatives Rejected
- **PostgreSQL / TimescaleDB**:
  - Row-oriented storage suffers severe write amplification under sustained throughput ($> 5,000\text{ spans/s}$ causes heavy WAL contention and high disk IOPS).
  - High compression ratios are impossible: storing JSON attributes and span events across 10M rows consumes $> 25\text{ GB}$ in Postgres vs $< 3\text{ GB}$ in ClickHouse with ZSTD compression.
  - Latency quantile aggregations over multi-million row tables trigger expensive sequential scans and RAM spikes.
- **Elasticsearch / OpenSearch**:
  - Heavy JVM memory footprint (minimum 4–8 GB heap) contradicts the 16 GB single-machine constraint.
  - High indexing CPU overhead and uncompressed inverted indices exhaust edge node disk storage.

## Consequences
- **Positive**:
  - Sustained local ingestion throughput $> 100,000\text{ spans/s}$ with zero queue backpressure.
  - Columnar compression yields $\approx 8\times$ disk space reduction compared to JSON row storage.
  - Analytical query latency for 10M spans runs at $p95 < 300\text{ ms}$.
  - Seamless integration with the official Grafana ClickHouse datasource plugin.
- **Negative**:
  - Introduces ClickHouse as an additional service in Docker Compose (`observe` profile).
  - Point-lookup updates and individual row deletes are not natively supported (handled by partition drops and TTLs).
