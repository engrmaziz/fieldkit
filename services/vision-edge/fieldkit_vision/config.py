"""Configuration settings for Vision Edge service."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class VisionEdgeSettings(BaseSettings):
    """Configuration for Vision Edge camera ingestion, metrics, and chaos testing."""

    environment: str = "development"
    port: int = 8005
    config_dir: str = os.getenv("VISION_CONFIG_DIR", "configs/cameras")
    video_dir: str = os.getenv("VISION_VIDEO_DIR", "data/p5/videos")

    # Ingestion & queue defaults
    default_fps: float = 5.0
    queue_maxsize: int = 4
    rtsp_timeout_sec: float = 5.0

    # Reconnection backoff
    reconnect_initial_backoff_sec: float = 1.0
    reconnect_max_backoff_sec: float = 30.0
    reconnect_multiplier: float = 2.0

    # Chaos testing flag (interval in seconds to simulate network drop; 0.0 = disabled)
    chaos_kill_interval_sec: float = float(os.getenv("VISION_CHAOS_KILL_INTERVAL_SEC", "0.0"))

    model_config = SettingsConfigDict(
        env_prefix="VISION_",
        env_file=".env",
        extra="ignore",
    )


settings = VisionEdgeSettings()
