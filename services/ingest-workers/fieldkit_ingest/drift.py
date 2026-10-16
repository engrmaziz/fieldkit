"""Deterministic Schema Drift Detection, Statistical Profiling, and LLM Rename Suggestions."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import duckdb
import psycopg
from fieldkit_llm.client import LLMClient
from pydantic import BaseModel, Field


class DriftSeverity(StrEnum):
    BLOCK = "BLOCK"
    WARN = "WARN"


class DriftEventType(StrEnum):
    COLUMN_REMOVED = "COLUMN_REMOVED"
    COLUMN_ADDED = "COLUMN_ADDED"
    DTYPE_CHANGED = "DTYPE_CHANGED"
    NULL_RATE_SPIKE = "NULL_RATE_SPIKE"
    NEW_ENUM_VALUE = "NEW_ENUM_VALUE"
    NUMERIC_P50_SHIFT = "NUMERIC_P50_SHIFT"


class RenameSuggestion(BaseModel):
    """Structured LLM output for column rename proposals."""

    old_name: str = Field(description="Name of the missing contract column")
    new_name: str = Field(description="Name of the newly discovered column")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reason: str = Field(description="Concise technical rationale for the mapping")


@dataclass
class DriftEvent:
    """Represents a detected schema, type, or statistical drift event."""

    event_id: str
    run_id: str
    source: str
    event_type: DriftEventType
    severity: DriftSeverity
    column_name: str
    details: dict[str, Any]
    suggestion: RenameSuggestion | None = None
    status: str = "open"  # open, suggested, approved, rejected
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Fingerprint:
    """Statistical and schema fingerprint of an ingestion batch."""

    run_id: str
    source: str
    row_count: int
    columns: list[dict[str, Any]]  # name, dtype, order
    null_rate: dict[str, float]
    distinct_count: dict[str, int]
    top_values: dict[str, list[str]]
    numeric_quantiles: dict[str, dict[str, float]]  # p01, p50, p99

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fingerprint:
        return cls(**data)


def compute_fingerprint(
    records: list[dict[str, Any]],
    source: str,
    run_id: str,
) -> Fingerprint:
    """Computes deterministic schema and statistical fingerprint from records."""
    if not records:
        return Fingerprint(
            run_id=run_id,
            source=source,
            row_count=0,
            columns=[],
            null_rate={},
            distinct_count={},
            top_values={},
            numeric_quantiles={},
        )

    row_count = len(records)
    first_row = records[0]
    col_names = [k for k in first_row.keys() if not k.startswith("_")]

    columns = []
    null_rate = {}
    distinct_count = {}
    top_values = {}
    numeric_quantiles = {}

    for idx, col in enumerate(col_names):
        vals = [r.get(col) for r in records]
        non_null_vals = [v for v in vals if v is not None and str(v).strip() != ""]
        null_c = row_count - len(non_null_vals)
        null_rate[col] = round(null_c / max(row_count, 1), 4)

        str_vals = [str(v) for v in non_null_vals]
        unique_vals = set(str_vals)
        distinct_count[col] = len(unique_vals)

        # Infer dtype
        def _try_float(val: Any) -> float | None:
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                pass
            try:
                return float(s.replace(".", "").replace(",", "."))
            except ValueError:
                return None

        numeric_vals: list[float] = []
        is_num = True
        if non_null_vals:
            for v in non_null_vals[:200]:
                parsed = _try_float(v)
                if parsed is None:
                    is_num = False
                    break
                numeric_vals.append(parsed)

        if is_num and numeric_vals:
            dtype = "numeric"
            all_nums = []
            for v in non_null_vals:
                parsed = _try_float(v)
                if parsed is not None:
                    all_nums.append(parsed)
            all_nums.sort()
            if all_nums:
                n = len(all_nums)
                p01 = all_nums[int(0.01 * (n - 1))]
                p50 = all_nums[int(0.50 * (n - 1))]
                p99 = all_nums[int(0.99 * (n - 1))]
                numeric_quantiles[col] = {"p01": round(p01, 2), "p50": round(p50, 2), "p99": round(p99, 2)}
        else:
            dtype = "string"

        columns.append({"order": idx, "name": col, "dtype": dtype})

        # Top values for categorical / low cardinality
        if len(unique_vals) <= 50 and non_null_vals:
            # Frequency count
            counts: dict[str, int] = {}
            for v in str_vals:
                counts[v] = counts.get(v, 0) + 1
            sorted_top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
            top_values[col] = [val for val, _ in sorted_top]

    return Fingerprint(
        run_id=run_id,
        source=source,
        row_count=row_count,
        columns=columns,
        null_rate=null_rate,
        distinct_count=distinct_count,
        top_values=top_values,
        numeric_quantiles=numeric_quantiles,
    )


class DriftRuleEngine:
    """Evaluates drift rules deterministically against contract and baseline fingerprint."""

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        # overrides map: source:old_col -> new_col
        self.overrides = overrides or {}

    def evaluate(
        self,
        current: Fingerprint,
        contract_columns: dict[str, Any],
        baseline: Fingerprint | None = None,
    ) -> list[DriftEvent]:
        events: list[DriftEvent] = []
        curr_col_map = {c["name"]: c for c in current.columns}

        # 1. Rule: Missing contract columns
        for col_name, spec in contract_columns.items():
            override_key = f"{current.source}:{col_name}"
            mapped_col = self.overrides.get(override_key)

            if col_name not in curr_col_map and (not mapped_col or mapped_col not in curr_col_map):
                required = spec.get("required", False)
                severity = DriftSeverity.BLOCK if required else DriftSeverity.WARN
                events.append(
                    DriftEvent(
                        event_id=f"drift_{uuid.uuid4().hex[:12]}",
                        run_id=current.run_id,
                        source=current.source,
                        event_type=DriftEventType.COLUMN_REMOVED,
                        severity=severity,
                        column_name=col_name,
                        details={
                            "message": f"Contract column '{col_name}' missing from payload",
                            "required": required,
                            "expected_dtype": spec.get("type", "str"),
                        },
                    )
                )

        # 2. Rule: Unexpected added columns
        for col_name, c_info in curr_col_map.items():
            if col_name not in contract_columns:
                # Check if this column is an approved target of an override
                is_override_target = any(
                    target == col_name and key.startswith(f"{current.source}:")
                    for key, target in self.overrides.items()
                )
                if not is_override_target:
                    events.append(
                        DriftEvent(
                            event_id=f"drift_{uuid.uuid4().hex[:12]}",
                            run_id=current.run_id,
                            source=current.source,
                            event_type=DriftEventType.COLUMN_ADDED,
                            severity=DriftSeverity.WARN,
                            column_name=col_name,
                            details={
                                "message": f"Unexpected new column '{col_name}' discovered",
                                "observed_dtype": c_info["dtype"],
                            },
                        )
                    )

        # 3. Rule: DType changes
        for col_name, spec in contract_columns.items():
            if col_name in curr_col_map:
                expected_type = spec.get("type", "str")
                observed_type = curr_col_map[col_name]["dtype"]

                if expected_type in ("float", "int", "numeric") and observed_type == "string":
                    events.append(
                        DriftEvent(
                            event_id=f"drift_{uuid.uuid4().hex[:12]}",
                            run_id=current.run_id,
                            source=current.source,
                            event_type=DriftEventType.DTYPE_CHANGED,
                            severity=DriftSeverity.BLOCK,
                            column_name=col_name,
                            details={
                                "message": f"Column '{col_name}' changed type: expected {expected_type}, observed {observed_type}",
                                "expected": expected_type,
                                "observed": observed_type,
                            },
                        )
                    )

        # 4. Statistical rules against baseline
        if baseline:
            # Null rate spike
            for col_name in contract_columns:
                if col_name in current.null_rate and col_name in baseline.null_rate:
                    curr_null = current.null_rate[col_name]
                    base_null = baseline.null_rate[col_name]
                    diff = curr_null - base_null
                    if diff > 0.15:  # Significant >15% spike
                        events.append(
                            DriftEvent(
                                event_id=f"drift_{uuid.uuid4().hex[:12]}",
                                run_id=current.run_id,
                                source=current.source,
                                event_type=DriftEventType.NULL_RATE_SPIKE,
                                severity=DriftSeverity.WARN,
                                column_name=col_name,
                                details={
                                    "message": f"Null rate for '{col_name}' spiked from {base_null:.2%} to {curr_null:.2%}",
                                    "base_null_rate": base_null,
                                    "curr_null_rate": curr_null,
                                },
                            )
                        )

            # Categorical new enum values
            for col_name, base_vals in baseline.top_values.items():
                if col_name in current.top_values and base_vals:
                    curr_vals = current.top_values[col_name]
                    new_enums = set(curr_vals) - set(base_vals)
                    if new_enums:
                        events.append(
                            DriftEvent(
                                event_id=f"drift_{uuid.uuid4().hex[:12]}",
                                run_id=current.run_id,
                                source=current.source,
                                event_type=DriftEventType.NEW_ENUM_VALUE,
                                severity=DriftSeverity.WARN,
                                column_name=col_name,
                                details={
                                    "message": f"Discovered new enum value(s) in '{col_name}': {sorted(new_enums)}",
                                    "new_values": list(new_enums),
                                },
                            )
                        )

            # Numeric median p50 shift > 50%
            for col_name, base_q in baseline.numeric_quantiles.items():
                if col_name in current.numeric_quantiles:
                    base_p50 = base_q.get("p50", 0.0)
                    curr_p50 = current.numeric_quantiles[col_name].get("p50", 0.0)
                    denom = max(abs(base_p50), 1.0)
                    shift = abs(curr_p50 - base_p50) / denom
                    if shift > 0.50:
                        events.append(
                            DriftEvent(
                                event_id=f"drift_{uuid.uuid4().hex[:12]}",
                                run_id=current.run_id,
                                source=current.source,
                                event_type=DriftEventType.NUMERIC_P50_SHIFT,
                                severity=DriftSeverity.WARN,
                                column_name=col_name,
                                details={
                                    "message": f"Numeric median (p50) shifted by {shift:.1%}: {base_p50} -> {curr_p50}",
                                    "base_p50": base_p50,
                                    "curr_p50": curr_p50,
                                    "shift_pct": round(shift * 100, 2),
                                },
                            )
                        )

        return events


class LLMRenameSuggester:
    """Invokes packages/llm to analyze removed vs added column pairs and generate rename proposals."""

    def __init__(self, prompt_template_path: str | Path | None = None) -> None:
        self.template_path = Path(
            prompt_template_path or "packages/llm/prompts/column_mapping.jinja"
        )
        self.llm_client = LLMClient()

    async def suggest_rename(
        self,
        source_name: str,
        old_col: str,
        old_dtype: str,
        old_samples: list[str],
        new_col: str,
        new_dtype: str,
        new_samples: list[str],
    ) -> RenameSuggestion:
        """Calls LLM with structured output schema to propose a column mapping."""
        # Clean fallback if LLM is offline or in testing
        try:
            suggestion = await self.llm_client.structured_output_from_template(
                template_path=self.template_path,
                schema_cls=RenameSuggestion,
                task="column_mapping",
                model=os.getenv("OLLAMA_MODEL_DEFAULT", "qwen3.5:4b"),
                temperature=0.0,
                source_name=source_name,
                old_column=old_col,
                old_dtype=old_dtype,
                old_samples=old_samples[:20],
                new_column=new_col,
                new_dtype=new_dtype,
                new_samples=new_samples[:20],
            )
            return suggestion
        except Exception:
            # Deterministic heuristic fallback
            sim_score = 0.0
            s_old = old_col.lower().replace("_", "").replace("-", "")
            s_new = new_col.lower().replace("_", "").replace("-", "")
            if s_old in s_new or s_new in s_old:
                sim_score = 0.85
            elif old_dtype == new_dtype and old_samples and new_samples:
                sim_score = 0.75
            else:
                sim_score = 0.40

            return RenameSuggestion(
                old_name=old_col,
                new_name=new_col,
                confidence=sim_score,
                reason=f"Heuristic name/type alignment (old: {old_col}, new: {new_col})",
            )


class DriftStore:
    """Persists drift events and human-approved column mapping overrides."""

    def __init__(
        self,
        postgres_dsn: str | None = None,
        fallback_dir: str | Path = "data/staging",
    ) -> None:
        self.postgres_dsn = postgres_dsn or os.getenv(
            "DATABASE_URL",
            "postgresql://fieldkit:fieldkit_dev_insecure@localhost:5432/fieldkit",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.fallback_path = Path(fallback_dir) / "drift.duckdb"
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._use_postgres = self._init_db()

    def _init_db(self) -> bool:
        try:
            with psycopg.connect(self.postgres_dsn, autocommit=True, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS drift_event (
                            event_id VARCHAR(64) PRIMARY KEY,
                            run_id VARCHAR(64) NOT NULL,
                            source VARCHAR(64) NOT NULL,
                            event_type VARCHAR(64) NOT NULL,
                            severity VARCHAR(32) NOT NULL,
                            column_name VARCHAR(128) NOT NULL,
                            details JSONB NOT NULL,
                            suggestion JSONB,
                            status VARCHAR(32) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS contract_override (
                            id SERIAL PRIMARY KEY,
                            source VARCHAR(64) NOT NULL,
                            old_column VARCHAR(128) NOT NULL,
                            new_column VARCHAR(128) NOT NULL,
                            approved_by VARCHAR(64) NOT NULL,
                            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(source, old_column)
                        );
                    """)
            return True
        except Exception:
            con = duckdb.connect(self.fallback_path.as_posix())
            con.execute("""
                CREATE TABLE IF NOT EXISTS drift_event (
                    event_id VARCHAR PRIMARY KEY,
                    run_id VARCHAR,
                    source VARCHAR,
                    event_type VARCHAR,
                    severity VARCHAR,
                    column_name VARCHAR,
                    details VARCHAR,
                    suggestion VARCHAR,
                    status VARCHAR,
                    created_at TIMESTAMP
                );
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS contract_override (
                    source VARCHAR,
                    old_column VARCHAR,
                    new_column VARCHAR,
                    approved_by VARCHAR,
                    approved_at TIMESTAMP
                );
            """)
            con.close()
            return False

    def save_events(self, events: list[DriftEvent]) -> None:
        if not events:
            return

        now = datetime.now()
        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        for e in events:
                            cur.execute(
                                """
                                INSERT INTO drift_event (event_id, run_id, source, event_type, severity, column_name, details, suggestion, status, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (event_id) DO UPDATE SET status = EXCLUDED.status;
                                """,
                                (
                                    e.event_id,
                                    e.run_id,
                                    e.source,
                                    e.event_type.value,
                                    e.severity.value,
                                    e.column_name,
                                    json.dumps(e.details),
                                    json.dumps(e.suggestion.model_dump()) if e.suggestion else None,
                                    e.status,
                                    now,
                                ),
                            )
                return
            except Exception:
                pass

        con = duckdb.connect(self.fallback_path.as_posix())
        for e in events:
            con.execute(
                """
                INSERT OR REPLACE INTO drift_event VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    e.event_id,
                    e.run_id,
                    e.source,
                    e.event_type.value,
                    e.severity.value,
                    e.column_name,
                    json.dumps(e.details),
                    json.dumps(e.suggestion.model_dump()) if e.suggestion else None,
                    e.status,
                    now,
                ),
            )
        con.close()

    def approve_mapping(self, event_id: str, approved_by: str = "analyst") -> bool:
        """Approves a suggested column mapping and stores override in contract_override."""
        now = datetime.now()

        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT source, suggestion FROM drift_event WHERE event_id = %s", (event_id,))
                        row = cur.fetchone()
                        if row and row[1]:
                            src = row[0]
                            sugg = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                            cur.execute(
                                """
                                INSERT INTO contract_override (source, old_column, new_column, approved_by, approved_at)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (source, old_column) DO UPDATE SET new_column = EXCLUDED.new_column, approved_at = EXCLUDED.approved_at;
                                """,
                                (src, sugg["old_name"], sugg["new_name"], approved_by, now),
                            )
                            cur.execute("UPDATE drift_event SET status = 'approved' WHERE event_id = %s", (event_id,))
                            return True
            except Exception:
                pass

        con = duckdb.connect(self.fallback_path.as_posix())
        row = con.execute("SELECT source, suggestion FROM drift_event WHERE event_id = ?", (event_id,)).fetchone()
        if row and row[1]:
            src = row[0]
            sugg = json.loads(row[1])
            con.execute(
                "INSERT INTO contract_override VALUES (?, ?, ?, ?, ?)",
                (src, sugg["old_name"], sugg["new_name"], approved_by, now),
            )
            con.execute("UPDATE drift_event SET status = 'approved' WHERE event_id = ?", (event_id,))
            con.close()
            return True
        con.close()
        return False

    def get_active_overrides(self, source: str) -> dict[str, str]:
        """Returns active {source:old_column -> new_column} overrides."""
        overrides: dict[str, str] = {}
        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT old_column, new_column FROM contract_override WHERE source = %s", (source,))
                        for old_c, new_c in cur.fetchall():
                            overrides[f"{source}:{old_c}"] = new_c
                return overrides
            except Exception:
                pass

        if self.fallback_path.exists():
            con = duckdb.connect(self.fallback_path.as_posix())
            rows = con.execute("SELECT old_column, new_column FROM contract_override WHERE source = ?", (source,)).fetchall()
            for old_c, new_c in rows:
                overrides[f"{source}:{old_c}"] = new_c
            con.close()

        return overrides
