"""Prometheus and operational metrics for camera workers."""

from __future__ import annotations

import time
from collections import deque

from prometheus_client import Counter, Gauge

from fieldkit_vision.models import CameraMetrics

# Prometheus metrics
CAMERA_DECODED_FPS = Gauge(
    "vision_camera_decoded_fps", "Raw decoded FPS from camera stream", ["camera_id"]
)
CAMERA_PROCESSED_FPS = Gauge(
    "vision_camera_processed_fps", "Sampled/processed FPS passed to queue", ["camera_id"]
)
CAMERA_DROPPED_FRAMES = Counter(
    "vision_camera_dropped_frames_total",
    "Frames dropped due to bounded queue backpressure",
    ["camera_id"],
)
CAMERA_RECONNECTS = Counter(
    "vision_camera_reconnects_total", "Stream reconnection attempts", ["camera_id"]
)
CAMERA_CONNECTED = Gauge(
    "vision_camera_connected", "Camera connection state (1=connected, 0=disconnected)", ["camera_id"]
)
VISION_ALERTS_TOTAL = Counter(
    "vision_alerts_total", "Safety and security violation alerts emitted", ["camera_id", "rule_type", "severity"]
)


class CameraMetricsTracker:
    """In-memory sliding window metrics tracker per camera feed."""

    def __init__(self, camera_id: str, window_seconds: float = 3.0) -> None:
        self.camera_id = camera_id
        self.window_seconds = window_seconds

        self._decoded_timestamps: deque[float] = deque()
        self._processed_timestamps: deque[float] = deque()

        self.dropped_frames: int = 0
        self.reconnects: int = 0
        self.total_decoded: int = 0
        self.total_processed: int = 0
        self.is_connected: bool = False
        self.last_frame_timestamp: float | None = None
        self.last_error: str | None = None

        # Initialize Prometheus metrics
        CAMERA_DECODED_FPS.labels(camera_id=self.camera_id).set(0.0)
        CAMERA_PROCESSED_FPS.labels(camera_id=self.camera_id).set(0.0)
        CAMERA_CONNECTED.labels(camera_id=self.camera_id).set(0)

    def record_decoded_frame(self, ts: float | None = None) -> None:
        now = ts or time.time()
        self.total_decoded += 1
        self.last_frame_timestamp = now
        self._decoded_timestamps.append(now)
        self._prune(self._decoded_timestamps, now)
        fps = self._calc_fps(self._decoded_timestamps)
        CAMERA_DECODED_FPS.labels(camera_id=self.camera_id).set(fps)

    def record_processed_frame(self, ts: float | None = None) -> None:
        now = ts or time.time()
        self.total_processed += 1
        self._processed_timestamps.append(now)
        self._prune(self._processed_timestamps, now)
        fps = self._calc_fps(self._processed_timestamps)
        CAMERA_PROCESSED_FPS.labels(camera_id=self.camera_id).set(fps)

    def record_dropped_frame(self) -> None:
        self.dropped_frames += 1
        CAMERA_DROPPED_FRAMES.labels(camera_id=self.camera_id).inc()

    def record_reconnect(self) -> None:
        self.reconnects += 1
        CAMERA_RECONNECTS.labels(camera_id=self.camera_id).inc()

    def set_connected(self, connected: bool, error: str | None = None) -> None:
        self.is_connected = connected
        if error is not None:
            self.last_error = error or "StreamConnectionError"
        elif connected:
            self.last_error = None
        CAMERA_CONNECTED.labels(camera_id=self.camera_id).set(1 if connected else 0)

    def _prune(self, q: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()

    def _calc_fps(self, q: deque[float]) -> float:
        if len(q) < 2:
            return float(len(q))
        duration = q[-1] - q[0]
        if duration <= 0.001:
            return float(len(q))
        return round((len(q) - 1) / duration, 2)

    def get_metrics(self) -> CameraMetrics:
        now = time.time()
        self._prune(self._decoded_timestamps, now)
        self._prune(self._processed_timestamps, now)
        return CameraMetrics(
            camera_id=self.camera_id,
            is_connected=self.is_connected,
            decoded_fps=self._calc_fps(self._decoded_timestamps),
            processed_fps=self._calc_fps(self._processed_timestamps),
            dropped_frames=self.dropped_frames,
            reconnects=self.reconnects,
            total_decoded=self.total_decoded,
            total_processed=self.total_processed,
            last_frame_timestamp=self.last_frame_timestamp,
            last_error=self.last_error,
        )
