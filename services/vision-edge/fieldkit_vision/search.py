"""Event Search, Parameterized Query Generation, and Natural Language Query Parser.

Translates structured and conversational safety queries into strictly validated EventFilter
schemas without SQL injection risk, targeting ClickHouse analytical storage and edge event buffers.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class EventFilter(BaseModel):
    """Schema-validated query filters for vision events."""

    camera_id: str | None = None
    rule_type: str | None = None
    severity: str | None = None
    from_ts: float | None = None
    to_ts: float | None = None
    person_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    cursor: str | None = None


class NLSearchRequest(BaseModel):
    """User conversational search inquiry."""

    query: str


class NLSearchResponse(BaseModel):
    """Parsed structured filter and explanation chips."""

    original_query: str
    parsed_filter: EventFilter
    filter_chips: list[str] = Field(default_factory=list)


def parse_nl_query_to_filter(query: str) -> tuple[EventFilter, list[str]]:
    """Parse a natural language query into a schema-validated EventFilter and UI chips.

    Uses deterministic token and regex extraction with fail-closed safety.
    """
    q_lower = query.lower().strip()
    chips: list[str] = []

    camera_id: str | None = None
    rule_type: str | None = None
    severity: str | None = None
    person_id: str | None = None

    # 1. Camera resolution
    if "press" in q_lower or "cam1" in q_lower or "stamping" in q_lower:
        camera_id = "cam1_press"
        chips.append("Camera: Press Bed (cam1)")
    elif "logistics" in q_lower or "cam2" in q_lower or "corridor" in q_lower:
        camera_id = "cam2_logistics"
        chips.append("Camera: Logistics Corridor (cam2)")
    elif "assembly" in q_lower or "cam3" in q_lower or "bay 4" in q_lower:
        camera_id = "cam3_assembly"
        chips.append("Camera: Assembly Bay (cam3)")
    elif "perimeter" in q_lower or "cam4" in q_lower or "gate" in q_lower:
        camera_id = "cam4_perimeter"
        chips.append("Camera: Perimeter Gate (cam4)")

    # 2. Rule type resolution
    if (
        "proximity" in q_lower
        or "forklift" in q_lower
        or "separation" in q_lower
        or "near" in q_lower
    ):
        rule_type = "forklift_pedestrian_proximity"
        chips.append("Rule: Proximity (<2.0m)")
    elif (
        "helmet" in q_lower
        or "ppe" in q_lower
        or "vest" in q_lower
        or "hard hat" in q_lower
        or "no_helmet" in q_lower
    ):
        rule_type = "zone_ppe_missing"
        chips.append("Rule: Missing PPE")
    elif "dwell" in q_lower or "loiter" in q_lower or "lingering" in q_lower:
        rule_type = "dwell"
        chips.append("Rule: Zone Dwell")
    elif "cross" in q_lower or "line" in q_lower or "perimeter" in q_lower or "boundary" in q_lower:
        rule_type = "line_cross"
        chips.append("Rule: Line Crossing")

    # 3. Severity resolution
    if "critical" in q_lower or "danger" in q_lower or "severe" in q_lower:
        severity = "CRITICAL"
        chips.append("Severity: CRITICAL")
    elif "warn" in q_lower or "warning" in q_lower:
        severity = "WARNING"
        chips.append("Severity: WARNING")

    # 4. Person ID pattern match (e.g. person_0001 or pid_12)
    pid_match = re.search(r"\b(person_\d{4}|pid_\d+)\b", q_lower)
    if pid_match:
        person_id = pid_match.group(1)
        chips.append(f"Person: {person_id}")

    flt = EventFilter(
        camera_id=camera_id,
        rule_type=rule_type,
        severity=severity,
        person_id=person_id,
        limit=50,
    )

    if not chips:
        chips.append("All Events (Unrestricted)")

    return flt, chips


def build_clickhouse_query(flt: EventFilter) -> tuple[str, dict[str, Any]]:
    """Generate parameterized ClickHouse SQL query enforcing type safety and avoiding injection."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": flt.limit}

    if flt.camera_id:
        conditions.append("camera_id = %(camera_id)s")
        params["camera_id"] = flt.camera_id
    if flt.rule_type:
        conditions.append("rule_type = %(rule_type)s")
        params["rule_type"] = flt.rule_type
    if flt.severity:
        conditions.append("severity = %(severity)s")
        params["severity"] = flt.severity
    if flt.from_ts is not None:
        conditions.append("timestamp >= %(from_ts)s")
        params["from_ts"] = flt.from_ts
    if flt.to_ts is not None:
        conditions.append("timestamp <= %(to_ts)s")
        params["to_ts"] = flt.to_ts

    sql = (
        f"SELECT event_id, camera_id, plant_id, zone_id, rule_id, rule_type, "
        f"severity, track_id, timestamp, duration_sec, confidence, metadata, clip_uri "
        f"FROM fieldkit_vision.events "
        f"WHERE {' AND '.join(conditions)} "
        f"ORDER BY timestamp DESC "
        f"LIMIT %(limit)s"
    )

    return sql, params
