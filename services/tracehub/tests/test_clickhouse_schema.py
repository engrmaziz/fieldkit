"""Unit tests verifying ClickHouse migration schema integrity."""

from pathlib import Path


def test_clickhouse_migration_schema_definitions() -> None:
    migration_path = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"
    assert migration_path.exists(), f"Migration file not found at {migration_path}"

    content = migration_path.read_text(encoding="utf-8")

    # 1. Database and tables exist
    assert "CREATE DATABASE IF NOT EXISTS fieldkit_tracehub" in content
    assert "CREATE TABLE IF NOT EXISTS fieldkit_tracehub.spans" in content
    assert "CREATE TABLE IF NOT EXISTS fieldkit_tracehub.metrics_1m" in content
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS fieldkit_tracehub.mv_spans_to_metrics_1m" in content
    assert "CREATE TABLE IF NOT EXISTS fieldkit_tracehub.kafka_spans_queue" in content

    # 2. Key analytical columns in spans table
    assert "trace_id String" in content
    assert "span_id String" in content
    assert "parent_span_id String" in content
    assert "duration_ms Float64" in content
    assert "input_tokens UInt32" in content
    assert "output_tokens UInt32" in content
    assert "model LowCardinality(String)" in content
    assert "task LowCardinality(String)" in content
    assert "prompt_version LowCardinality(String)" in content
    assert "route LowCardinality(String)" in content
    assert "plant LowCardinality(String)" in content
    assert "attributes Map(String, String)" in content
    assert "events String" in content

    # 3. Aggregations and quantiles in metrics_1m
    assert "AggregateFunction(quantiles(0.5, 0.9, 0.95, 0.99), Float64)" in content
    assert "quantilesState(0.5, 0.9, 0.95, 0.99)(duration_ms)" in content
    assert "AggregatingMergeTree()" in content
