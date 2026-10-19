"""Pydantic schemas and response models for Tracehub API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpanRecord(BaseModel):
    """Flat span representation matching the ClickHouse spans table."""

    trace_id: str
    span_id: str
    parent_span_id: str = ""
    service: str
    name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str
    status_message: str = ""
    model: str = ""
    task: str = ""
    prompt_version: str = ""
    route: str = ""
    plant: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    attributes: dict[str, str] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class SpanTreeNode(BaseModel):
    """Hierarchical node for trace waterfall visualization."""

    span_id: str
    parent_span_id: str = ""
    name: str
    service: str
    status: str
    duration_ms: float
    relative_start_ms: float = 0.0
    model: str = ""
    task: str = ""
    prompt_version: str = ""
    route: str = ""
    plant: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    attributes: dict[str, str] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    children: list[SpanTreeNode] = Field(default_factory=list)


class TraceSummary(BaseModel):
    """Summarized trace entry for trace search and list tables."""

    trace_id: str
    root_span_name: str
    service: str
    status: str
    start_time: datetime
    duration_ms: float
    total_spans: int = 1
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    model: str = ""
    task: str = ""
    route: str = ""
    plant: str = ""


class TraceListResponse(BaseModel):
    """Paginated response for trace search."""

    traces: list[TraceSummary]
    total: int
    cursor: str | None = None


class TraceTreeResponse(BaseModel):
    """Full hierarchical span tree for a single trace."""

    trace_id: str
    total_duration_ms: float
    total_spans: int
    root: SpanTreeNode | None


class MetricDataPoint(BaseModel):
    """Single point in a time series."""

    timestamp: datetime
    value: float
    count: int = 1


class MetricSeriesResponse(BaseModel):
    """Time-series aggregation for latency, errors, or tokens."""

    series_name: str
    service: str | None = None
    task: str | None = None
    step: str = "1m"
    points: list[MetricDataPoint]
