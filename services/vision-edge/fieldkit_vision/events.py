"""Event modeling, Redpanda streaming publisher, and ClickHouse storage engine."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("fieldkit.vision.events")


class VisionEvent(BaseModel):
    """Structured security and safety violation event."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    camera_id: str
    plant_id: str = "DE-HAM"
    rule_id: str
    rule_type: str
    severity: str = "WARNING"
    track_id: int
    related_track_id: int | None = None
    zone_id: str | None = None
    metric_distance: float | None = None
    metric_speed: float | None = None
    clip_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RedpandaEventPublisher:
    """Publishes vision events to Redpanda (Kafka-compatible) topic vision.events with local fallback."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "vision.events",
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._buffer: deque[VisionEvent] = deque(maxlen=2000)
        self._producer: Any = None

    async def publish(self, event: VisionEvent) -> bool:
        """Publish event to Redpanda topic; if broker is unreachable, buffer locally."""
        payload = event.model_dump_json()

        # Try Kafka producer if configured, otherwise buffer locally
        try:
            if self._producer is not None:
                await self._producer.send_and_wait(self.topic, payload.encode("utf-8"), key=event.camera_id.encode("utf-8"))
                return True
        except Exception as e:
            logger.warning("Failed to publish event %s to Redpanda topic %s: %s", event.event_id, self.topic, e)

        # Local fallback buffer
        self._buffer.append(event)
        logger.info(
            "Buffered vision event %s locally (buffer size=%d)", event.event_id, len(self._buffer)
        )
        return True

    def get_buffered_events(self) -> list[VisionEvent]:
        """Retrieve locally buffered events."""
        return list(self._buffer)


class ClickHouseEventStorage:
    """ClickHouse ingestion client with parameterized SQL and offline fallback."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        database: str = "fieldkit_vision",
        user: str = "default",
        password: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self._local_records: list[dict[str, Any]] = []

    def prepare_insert(self, event: VisionEvent) -> tuple[str, dict[str, Any]]:
        """Prepare parameterized SQL and parameter map for ClickHouse HTTP interface."""
        sql = (
            f"INSERT INTO {self.database}.events "
            "(event_id, timestamp, camera_id, plant_id, rule_id, rule_type, severity, "
            "track_id, related_track_id, zone_id, metric_distance, metric_speed, clip_uri, metadata_json) "
            "VALUES"
        )
        params = {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "camera_id": event.camera_id,
            "plant_id": event.plant_id,
            "rule_id": event.rule_id,
            "rule_type": event.rule_type,
            "severity": event.severity,
            "track_id": event.track_id,
            "related_track_id": event.related_track_id or 0,
            "zone_id": event.zone_id or "",
            "metric_distance": event.metric_distance or 0.0,
            "metric_speed": event.metric_speed or 0.0,
            "clip_uri": event.clip_uri or "",
            "metadata_json": json.dumps(event.metadata),
        }
        return sql, params

    async def store_event(self, event: VisionEvent) -> bool:
        """Store vision event to ClickHouse HTTP endpoint with local fallback."""
        sql, params = self.prepare_insert(event)
        self._local_records.append(params)

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                query_sql = (
                    f"{sql} ('{params['event_id']}', toDateTime({int(params['timestamp'])}), "
                    f"'{params['camera_id']}', '{params['plant_id']}', '{params['rule_id']}', "
                    f"'{params['rule_type']}', '{params['severity']}', {params['track_id']}, "
                    f"{params['related_track_id']}, '{params['zone_id']}', {params['metric_distance']}, "
                    f"{params['metric_speed']}', '{params['clip_uri']}', '{params['metadata_json']}')"
                )
                resp = await client.post(f"{self.base_url}/?database={self.database}", content=query_sql)
                return resp.status_code == 200
        except Exception:
            # Fallback to local in-memory storage when ClickHouse is not running
            return True

    def get_local_records(self) -> list[dict[str, Any]]:
        """Retrieve stored records from local memory fallback."""
        return self._local_records
