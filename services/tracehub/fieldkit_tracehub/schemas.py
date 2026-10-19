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


# ============================================================================
# Prompt Registry Schemas
# ============================================================================

class PromptCreate(BaseModel):
    """Payload to register a versioned prompt."""

    name: str
    version: str
    template: str
    sha256: str
    package: str = "fieldkit"


class PromptRecord(BaseModel):
    """Stored record for a specific prompt version."""

    name: str
    version: str
    template: str
    sha256: str
    package: str
    created_at: datetime


class PromptSummary(BaseModel):
    """Catalog summary of a prompt and its known versions."""

    name: str
    active_version: str
    total_versions: int
    versions: list[str]
    package: str
    updated_at: datetime


class PromptVersionDiff(BaseModel):
    """Line-by-line unified diff between two prompt versions."""

    name: str
    v1: str
    v2: str
    diff_text: str
    additions: int
    deletions: int


# ============================================================================
# Eval Runs & Regression Comparison Schemas
# ============================================================================

class EvalItem(BaseModel):
    """Individual benchmark question/attack evaluation result."""

    id: str
    question: str
    scores: dict[str, float] = Field(default_factory=dict)
    output: str = ""
    trace_id: str = ""
    passed: bool = True


class EvalRunCreate(BaseModel):
    """Payload to publish an evaluation benchmark run."""

    run_id: str | None = None
    suite: str
    model: str
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    git_sha: str = ""
    items: list[EvalItem] = Field(default_factory=list)
    aggregates: dict[str, float] = Field(default_factory=dict)


class EvalRunSummary(BaseModel):
    """High-level summary of an evaluation run for run lists."""

    run_id: str
    suite: str
    model: str
    prompt_versions: dict[str, str]
    git_sha: str
    total_items: int
    aggregates: dict[str, float]
    timestamp: datetime


class EvalRunDetail(BaseModel):
    """Complete evaluation run record including all item-level outputs."""

    run_id: str
    suite: str
    model: str
    prompt_versions: dict[str, str]
    git_sha: str
    total_items: int
    aggregates: dict[str, float]
    timestamp: datetime
    items: list[EvalItem]


class MetricDeltaWithCI(BaseModel):
    """Aggregate metric delta with 95% bootstrap confidence interval."""

    metric: str
    baseline_score: float
    candidate_score: float
    delta: float
    ci_lower: float
    ci_upper: float
    significant: bool


class ItemRegression(BaseModel):
    """Individual item where candidate score dropped vs baseline."""

    item_id: str
    question: str
    metric: str
    baseline_score: float
    candidate_score: float
    delta: float
    trace_id: str = ""


class EvalComparisonResponse(BaseModel):
    """Item-by-item comparison and statistical significance between two eval runs."""

    baseline_id: str
    candidate_id: str
    suite: str
    metric_deltas: dict[str, MetricDeltaWithCI]
    regressions: list[ItemRegression]
    improvements: list[ItemRegression]
    total_items_compared: int
    total_regressions: int
    total_improvements: int
    total_unchanged: int


# ============================================================================
# A/B Experiments Schemas
# ============================================================================

class ExperimentVariant(BaseModel):
    """Single variant arm in an online A/B experiment."""

    name: str
    model: str
    prompt_version: str
    pct: int = Field(ge=0, le=100, description="Percentage of traffic allocated (0-100)")


class ExperimentCreate(BaseModel):
    """Payload to create or update an A/B experiment."""

    name: str
    task: str
    variants: list[ExperimentVariant]
    status: str = "active"
    description: str = ""


class ExperimentRecord(BaseModel):
    """Stored definition and state of an A/B experiment."""

    name: str
    task: str
    variants: list[ExperimentVariant]
    status: str
    description: str
    created_at: datetime
    updated_at: datetime


class ExperimentConfigResponse(BaseModel):
    """Lightweight config response cached by LLM clients for variant routing."""

    name: str
    task: str
    status: str
    variants: list[ExperimentVariant]


class ExperimentResolveRequest(BaseModel):
    """Request payload to deterministically assign a user to an experiment variant."""

    user_id: str


class ExperimentResolveResponse(BaseModel):
    """Resolved model and prompt version assignment for a user."""

    experiment_name: str
    variant_name: str
    model: str
    prompt_version: str
    user_id: str


class VariantMetricResult(BaseModel):
    """Observed operational and feedback telemetry for a specific variant arm."""

    variant_name: str
    model: str
    prompt_version: str
    total_spans: int
    p50_latency_ms: float
    p95_latency_ms: float
    error_rate: float
    avg_tokens: float
    feedback_thumbs_up: int
    feedback_thumbs_down: int
    satisfaction_rate: float


class ExperimentResultsResponse(BaseModel):
    """Aggregated evaluation telemetry and automated stop-rule status for an A/B test."""

    experiment_name: str
    status: str
    task: str
    variants: list[VariantMetricResult]
    stop_rule_triggered: bool
    stop_rule_reason: str | None = None
    metric_deltas: dict[str, MetricDeltaWithCI] = Field(default_factory=dict)


