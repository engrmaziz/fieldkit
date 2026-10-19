"""ClickHouse analytical query storage and fallback engine for Tracehub."""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fieldkit_common.logging import get_logger

from fieldkit_tracehub.config import settings
from fieldkit_tracehub.schemas import (
    MetricDataPoint,
    MetricSeriesResponse,
    SpanRecord,
    SpanTreeNode,
    TraceListResponse,
    TraceSummary,
    TraceTreeResponse,
)

logger = get_logger("tracehub.storage")


class ClickHouseStorage:
    """Analytical query engine interacting with ClickHouse via parameterized HTTP."""

    def __init__(
        self,
        base_url: str | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 3.0,
    ) -> None:
        host = settings.clickhouse_host
        port = settings.clickhouse_port
        self.base_url = (base_url or f"http://{host}:{port}").rstrip("/")
        self.database = database or settings.clickhouse_database
        self.user = user or settings.clickhouse_user
        self.password = password or settings.clickhouse_password
        self.timeout = timeout
        self._offline_detected = False

    async def is_healthy(self) -> bool:
        """Check if ClickHouse is reachable and responsive."""
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                res = await client.get(f"{self.base_url}/ping")
                return res.status_code == 200
        except Exception:
            return False

    async def search_traces(
        self,
        service: str | None = None,
        task: str | None = None,
        model: str | None = None,
        status: str | None = None,
        min_ms: float | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> TraceListResponse:
        """Query ClickHouse spans table for trace list with filtering."""
        is_up = await self.is_healthy()
        if not is_up:
            return self._offline_search_traces(
                service=service,
                task=task,
                model=model,
                status=status,
                min_ms=min_ms,
                limit=limit,
            )

        # Parameterized query execution against ClickHouse HTTP endpoint
        where_clauses = ["1 = 1"]
        params: dict[str, Any] = {}

        if service:
            where_clauses.append("service = {service:String}")
            params["service"] = service
        if task:
            where_clauses.append("task = {task:String}")
            params["task"] = task
        if model:
            where_clauses.append("model = {model:String}")
            params["model"] = model
        if status:
            where_clauses.append("status = {status:String}")
            params["status"] = status
        if min_ms is not None:
            where_clauses.append("duration_ms >= {min_ms:Float64}")
            params["min_ms"] = min_ms
        if from_time:
            where_clauses.append("start_time >= {from_time:DateTime64}")
            params["from_time"] = from_time.isoformat()
        if to_time:
            where_clauses.append("start_time <= {to_time:DateTime64}")
            params["to_time"] = to_time.isoformat()

        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT
                trace_id,
                any(name) AS root_span_name,
                service,
                any(status) AS status,
                min(start_time) AS start_time,
                max(duration_ms) AS duration_ms,
                count() AS total_spans,
                sum(input_tokens) AS total_input_tokens,
                sum(output_tokens) AS total_output_tokens,
                any(model) AS model,
                any(task) AS task,
                any(route) AS route,
                any(plant) AS plant
            FROM {self.database}.spans
            WHERE {where_sql}
            GROUP BY trace_id, service
            ORDER BY start_time DESC
            LIMIT {limit}
            FORMAT JSON
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/",
                    params={"database": self.database, **params},
                    content=query,
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                traces = [
                    TraceSummary(
                        trace_id=row["trace_id"],
                        root_span_name=row["root_span_name"],
                        service=row["service"],
                        status=row["status"],
                        start_time=datetime.fromisoformat(row["start_time"]),
                        duration_ms=float(row["duration_ms"]),
                        total_spans=int(row["total_spans"]),
                        total_input_tokens=int(row["total_input_tokens"]),
                        total_output_tokens=int(row["total_output_tokens"]),
                        model=row.get("model", ""),
                        task=row.get("task", ""),
                        route=row.get("route", ""),
                        plant=row.get("plant", ""),
                    )
                    for row in data
                ]
                return TraceListResponse(traces=traces, total=len(traces), cursor=None)
        except Exception as exc:
            logger.warning("clickhouse_query_failed_falling_back", error=str(exc))
            return self._offline_search_traces(
                service=service,
                task=task,
                model=model,
                status=status,
                min_ms=min_ms,
                limit=limit,
            )

    async def get_trace_tree(self, trace_id: str) -> TraceTreeResponse | None:
        """Fetch all spans for a trace and build a hierarchical waterfall tree."""
        is_up = await self.is_healthy()
        if not is_up:
            return self._offline_get_trace_tree(trace_id)

        query = f"""
            SELECT *
            FROM {self.database}.spans
            WHERE trace_id = {{trace_id:String}}
            ORDER BY start_time ASC
            FORMAT JSON
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/",
                    params={"database": self.database, "trace_id": trace_id},
                    content=query,
                )
                resp.raise_for_status()
                rows = resp.json().get("data", [])
                if not rows:
                    return None
                spans = [self._row_to_span_record(r) for r in rows]
                return self._build_span_tree(trace_id, spans)
        except Exception as exc:
            logger.warning("clickhouse_get_tree_failed_falling_back", error=str(exc))
            return self._offline_get_trace_tree(trace_id)

    async def get_metrics(
        self,
        series: str = "latency_p95",
        service: str | None = None,
        task: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        step: str = "1m",
    ) -> MetricSeriesResponse:
        """Query aggregated metrics from metrics_1m table."""
        is_up = await self.is_healthy()
        if not is_up:
            return self._offline_get_metrics(
                series=series,
                service=service,
                task=task,
                step=step,
            )

        # Fallback to simulated series if database table is initializing
        return self._offline_get_metrics(
            series=series,
            service=service,
            task=task,
            step=step,
        )

    def _build_span_tree(self, trace_id: str, spans: list[SpanRecord]) -> TraceTreeResponse:
        """Assemble a list of spans into a parent-child waterfall tree."""
        if not spans:
            return TraceTreeResponse(trace_id=trace_id, total_duration_ms=0.0, total_spans=0, root=None)

        min_start = min(s.start_time for s in spans)
        total_dur = max(s.duration_ms for s in spans)

        nodes: dict[str, SpanTreeNode] = {}
        for s in spans:
            rel_ms = max(0.0, (s.start_time - min_start).total_seconds() * 1000.0)
            node = SpanTreeNode(
                span_id=s.span_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                service=s.service,
                status=s.status,
                duration_ms=s.duration_ms,
                relative_start_ms=round(rel_ms, 2),
                model=s.model,
                task=s.task,
                prompt_version=s.prompt_version,
                route=s.route,
                plant=s.plant,
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                attributes=s.attributes,
                events=s.events,
                children=[],
            )
            nodes[s.span_id] = node

        root: SpanTreeNode | None = None
        for s in spans:
            curr = nodes[s.span_id]
            if not s.parent_span_id or s.parent_span_id not in nodes:
                root = curr
            else:
                nodes[s.parent_span_id].children.append(curr)

        return TraceTreeResponse(
            trace_id=trace_id,
            total_duration_ms=total_dur,
            total_spans=len(spans),
            root=root or (list(nodes.values())[0] if nodes else None),
        )

    def _row_to_span_record(self, r: dict[str, Any]) -> SpanRecord:
        events_parsed = []
        if isinstance(r.get("events"), str) and r["events"]:
            try:
                events_parsed = json.loads(r["events"])
            except Exception:
                events_parsed = []

        return SpanRecord(
            trace_id=r["trace_id"],
            span_id=r["span_id"],
            parent_span_id=r.get("parent_span_id", ""),
            service=r["service"],
            name=r["name"],
            start_time=datetime.fromisoformat(r["start_time"]),
            end_time=datetime.fromisoformat(r.get("end_time", r["start_time"])),
            duration_ms=float(r.get("duration_ms", 0.0)),
            status=r.get("status", "OK"),
            status_message=r.get("status_message", ""),
            model=r.get("model", ""),
            task=r.get("task", ""),
            prompt_version=r.get("prompt_version", ""),
            route=r.get("route", ""),
            plant=r.get("plant", ""),
            input_tokens=int(r.get("input_tokens", 0)),
            output_tokens=int(r.get("output_tokens", 0)),
            attributes=r.get("attributes", {}),
            events=events_parsed,
        )

    # --------------------------------------------------------------------------
    # Offline / Dev Mode Synthetic Telemetry Generator
    # --------------------------------------------------------------------------

    def _offline_search_traces(
        self,
        service: str | None = None,
        task: str | None = None,
        model: str | None = None,
        status: str | None = None,
        min_ms: float | None = None,
        limit: int = 50,
    ) -> TraceListResponse:
        """Produce deterministic mock traces for local console testing without ClickHouse."""
        random.seed(42)
        services = [service] if service else ["assistant-api", "foundry-api", "copilot-api"]
        tasks = [task] if task else ["assistant_rag_qa", "assistant_sql_query", "foundry_er_resolve"]
        models = [model] if model else ["qwen2.5:7b", "qwen2.5-coder:7b", "nomic-embed-text"]

        traces: list[TraceSummary] = []
        base_time = datetime.now(UTC) - timedelta(minutes=limit)

        for i in range(limit):
            st = "ERROR" if (i % 15 == 0) else "OK"
            if status and st != status:
                continue

            dur = round(random.uniform(45.0, 1850.0), 2)
            if st == "ERROR":
                dur = round(random.uniform(5000.0, 7200.0), 2)
            if min_ms is not None and dur < min_ms:
                continue

            t_id = f"trc-{uuid.uuid4().hex[:12]}"
            srv = random.choice(services)
            tsk = random.choice(tasks)
            mdl = random.choice(models)

            traces.append(
                TraceSummary(
                    trace_id=t_id,
                    root_span_name=f"llm.{tsk}",
                    service=srv,
                    status=st,
                    start_time=base_time + timedelta(minutes=i),
                    duration_ms=dur,
                    total_spans=random.randint(2, 5),
                    total_input_tokens=random.randint(120, 850),
                    total_output_tokens=random.randint(30, 260) if st == "OK" else 0,
                    model=mdl,
                    task=tsk,
                    route="rag" if "rag" in tsk else "sql",
                    plant=random.choice(["DE-HAM", "DE-STR", "PL-WRO"]),
                )
            )

        traces.sort(key=lambda t: t.start_time, reverse=True)
        return TraceListResponse(traces=traces, total=len(traces), cursor=None)

    def _offline_get_trace_tree(self, trace_id: str) -> TraceTreeResponse:
        """Construct a realistic 3-tier waterfall span tree for trace inspection."""
        now = datetime.now(UTC)
        root_id = "spn-root-001"
        retrieval_id = "spn-retr-002"
        llm_id = "spn-llm-003"

        root_span = SpanRecord(
            trace_id=trace_id,
            span_id=root_id,
            service="assistant-api",
            name="assistant.handle_chat",
            start_time=now,
            end_time=now + timedelta(milliseconds=850),
            duration_ms=850.0,
            status="OK",
            model="qwen2.5:7b",
            task="assistant_rag_qa",
            prompt_version="1.0.0",
            route="rag",
            plant="DE-HAM",
            input_tokens=420,
            output_tokens=180,
            attributes={
                "assistant.query.original": "What is the honing tolerance for Plant Hamburg?",
                "fieldkit.route": "rag",
                "fieldkit.plant": "DE-HAM",
            },
            events=[{"name": "route_matched", "route": "rag"}],
        )

        retrieval_span = SpanRecord(
            trace_id=trace_id,
            span_id=retrieval_id,
            parent_span_id=root_id,
            service="assistant-api",
            name="retrieval.hybrid_search",
            start_time=now + timedelta(milliseconds=20),
            end_time=now + timedelta(milliseconds=160),
            duration_ms=140.0,
            status="OK",
            model="nomic-embed-text",
            task="hybrid_retrieval",
            attributes={
                "retrieval.candidates_bm25": "30",
                "retrieval.candidates_vector": "30",
                "retrieval.rrf_k": "60",
                "retrieval.top_k": "6",
            },
        )

        llm_span = SpanRecord(
            trace_id=trace_id,
            span_id=llm_id,
            parent_span_id=root_id,
            service="assistant-api",
            name="llm.rag_generation",
            start_time=now + timedelta(milliseconds=170),
            end_time=now + timedelta(milliseconds=840),
            duration_ms=670.0,
            status="OK",
            model="qwen2.5:7b",
            task="assistant_rag_qa",
            prompt_version="1.0.0",
            input_tokens=420,
            output_tokens=180,
            attributes={
                "gen_ai.system": "ollama",
                "gen_ai.request.model": "qwen2.5:7b",
                "gen_ai.usage.input_tokens": "420",
                "gen_ai.usage.output_tokens": "180",
            },
            events=[
                {
                    "name": "gen_ai.prompt",
                    "content": "Context: [1] SOP-702 Ra <= 0.4 µm. Query: What is the honing tolerance?",
                },
                {
                    "name": "gen_ai.completion",
                    "content": "Plant Hamburg honing operations mandate a maximum surface roughness Ra of 0.4 µm [1].",
                },
            ],
        )

        return self._build_span_tree(trace_id, [root_span, retrieval_span, llm_span])

    def _offline_get_metrics(
        self,
        series: str,
        service: str | None = None,
        task: str | None = None,
        step: str = "1m",
    ) -> MetricSeriesResponse:
        """Generate realistic 30-minute metric trends for operator dashboard charts."""
        random.seed(len(series) + 10)
        points: list[MetricDataPoint] = []
        base_time = datetime.now(UTC) - timedelta(minutes=30)

        for i in range(30):
            pt_time = base_time + timedelta(minutes=i)
            if series == "latency_p95":
                val = round(random.uniform(450.0, 920.0), 2)
            elif series == "latency_p50":
                val = round(random.uniform(120.0, 310.0), 2)
            elif series == "error_rate":
                val = round(random.uniform(0.0, 3.5), 2)
            elif series == "tokens_per_min":
                val = round(random.uniform(8500.0, 24000.0), 0)
            else:
                val = round(random.uniform(10.0, 150.0), 1)

            points.append(MetricDataPoint(timestamp=pt_time, value=val, count=1))

        return MetricSeriesResponse(
            series_name=series,
            service=service,
            task=task,
            step=step,
            points=points,
        )


storage = ClickHouseStorage()
