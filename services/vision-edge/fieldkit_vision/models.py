"""Pydantic data models for camera configurations, frame streaming, and metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class ZoneConfig(BaseModel):
    """Polygon zone definition for rules and spatial analytics."""

    id: str
    name: str
    type: str = "generic"
    required_ppe: list[str] = Field(default_factory=list)
    polygon: list[list[int]] = Field(default_factory=list)


class HomographyConfig(BaseModel):
    """4-point floor plane homography calibration (pixels to meters)."""

    image_points: list[list[float]] = Field(default_factory=list)
    floor_points_meters: list[list[float]] = Field(default_factory=list)


class RuleConfig(BaseModel):
    """Rule definition for safety violations and tracking."""

    id: str
    type: str
    zone_id: str | None = None
    ppe_class: str | None = None
    min_violation_ratio: float = 0.70
    window_sec: float = 2.0
    cooldown_sec: float = 30.0
    class_a: str | None = None
    class_b: str | None = None
    max_distance_meters: float | None = None
    min_duration_sec: float | None = None
    min_forklift_speed_mps: float | None = None
    min_dwell_sec: float | None = None
    line: list[list[int]] | None = None
    direction: str | None = None


class CameraReconnectConfig(BaseModel):
    """Stream reconnection and backoff configuration."""

    initial_backoff_sec: float = 1.0
    max_backoff_sec: float = 30.0
    backoff_multiplier: float = 2.0
    timeout_sec: float = 5.0


class CameraQueueConfig(BaseModel):
    """Bounded frame buffer configuration."""

    maxsize: int = 4
    drop_policy: str = "drop_oldest"


class CameraConfig(BaseModel):
    """Per-camera configuration schema matching YAML format."""

    camera_id: str
    name: str
    plant_id: str = "DE-HAM"
    rtsp_url: str
    fallback_url: str | None = None
    target_fps: float = 5.0
    width: int = 1920
    height: int = 1080
    reconnect: CameraReconnectConfig = Field(default_factory=CameraReconnectConfig)
    queue: CameraQueueConfig = Field(default_factory=CameraQueueConfig)
    zones: list[ZoneConfig] = Field(default_factory=list)
    homography: HomographyConfig | None = None
    rules: list[RuleConfig] = Field(default_factory=list)


class FramePacket(BaseModel):
    """Decoded and timestamped video frame packet."""

    camera_id: str
    timestamp: float
    frame_index: int
    image: Any  # numpy.ndarray (uint8)
    width: int
    height: int

    model_config = {"arbitrary_types_allowed": True}

    @property
    def ndarray(self) -> np.ndarray:
        return self.image  # type: ignore[no-any-return]


class CameraMetrics(BaseModel):
    """Real-time operational metrics for an ingest worker."""

    camera_id: str
    is_connected: bool = False
    decoded_fps: float = 0.0
    processed_fps: float = 0.0
    dropped_frames: int = 0
    reconnects: int = 0
    total_decoded: int = 0
    total_processed: int = 0
    last_frame_timestamp: float | None = None
    last_error: str | None = None


class CameraHealthStatus(BaseModel):
    """Overall health diagnostic for camera streaming."""

    camera_id: str
    status: str  # "healthy", "degraded", "offline"
    metrics: CameraMetrics


class TrackResponse(BaseModel):
    """Active multi-object tracked entity with PPE compliance and metric coordinates."""

    track_id: int
    camera_id: str
    class_id: int
    class_name: str
    box: list[float]
    confidence: float
    foot_point: tuple[float, float]
    head_region: list[float]
    torso_region: list[float]
    floor_coord: tuple[float, float] | None = None
    is_wearing_helmet: bool = False
    is_wearing_vest: bool = False
    helmet_compliance_ratio: float = 0.0
    vest_compliance_ratio: float = 0.0
    speed_mps: float = 0.0

