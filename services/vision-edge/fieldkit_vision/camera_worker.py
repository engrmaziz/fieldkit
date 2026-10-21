"""Robust per-camera video ingestion worker with timestamp sampling and bounded queues."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from pathlib import Path

import cv2
import yaml

from fieldkit_vision.config import settings
from fieldkit_vision.metrics import CameraMetricsTracker
from fieldkit_vision.models import CameraConfig, FramePacket

logger = logging.getLogger("fieldkit.vision.worker")


class TimestampSampler:
    """Samples frames to a target FPS strictly based on timestamps rather than frame indices."""

    def __init__(self, target_fps: float = 5.0) -> None:
        self.target_fps = target_fps
        self.interval = 1.0 / max(target_fps, 0.1)
        self.last_sampled_ts: float | None = None

    def should_sample(self, timestamp: float) -> bool:
        """Return True if frame at timestamp should be sampled under target FPS."""
        if self.last_sampled_ts is None:
            self.last_sampled_ts = timestamp
            return True

        dt = timestamp - self.last_sampled_ts

        # Handle stream loop / backwards jump
        if dt < -0.1:
            self.last_sampled_ts = timestamp
            return True

        # Jitter tolerance: sample if dt >= interval - 0.005s
        if dt >= (self.interval - 0.005):
            self.last_sampled_ts = timestamp
            return True

        return False

    def reset(self) -> None:
        self.last_sampled_ts = None


class BoundedFrameQueue:
    """Bounded asyncio frame queue enforcing drop-oldest policy under consumer backpressure."""

    def __init__(self, maxsize: int = 4, metrics_tracker: CameraMetricsTracker | None = None) -> None:
        self.maxsize = max(maxsize, 1)
        self._queue: asyncio.Queue[FramePacket] = asyncio.Queue(maxsize=self.maxsize)
        self.metrics_tracker = metrics_tracker

    def put_drop_oldest(self, packet: FramePacket) -> bool:
        """Put frame into queue; if full, drops oldest frame first."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
                if self.metrics_tracker:
                    self.metrics_tracker.record_dropped_frame()
            except asyncio.QueueEmpty:
                pass

        try:
            self._queue.put_nowait(packet)
            return True
        except asyncio.QueueFull:
            # Under extreme concurrent race, drop current
            if self.metrics_tracker:
                self.metrics_tracker.record_dropped_frame()
            return False

    async def get(self) -> FramePacket:
        """Retrieve next frame packet asynchronously."""
        return await self._queue.get()

    def get_nowait(self) -> FramePacket | None:
        """Retrieve next frame packet synchronously without blocking."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()


class CameraWorker:
    """Resilient camera ingest worker with TCP RTSP, backoff reconnects, and chaos testing."""

    def __init__(
        self,
        config: CameraConfig,
        metrics_tracker: CameraMetricsTracker | None = None,
        chaos_kill_interval_sec: float | None = None,
    ) -> None:
        self.config = config
        self.metrics = metrics_tracker or CameraMetricsTracker(config.camera_id)
        self.sampler = TimestampSampler(target_fps=config.target_fps)
        self.queue = BoundedFrameQueue(
            maxsize=config.queue.maxsize, metrics_tracker=self.metrics
        )
        self.chaos_kill_interval_sec = (
            chaos_kill_interval_sec
            if chaos_kill_interval_sec is not None
            else settings.chaos_kill_interval_sec
        )

        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._latest_frame: FramePacket | None = None
        self._reconnect_attempts = 0
        self._connected_at: float | None = None

    @property
    def latest_frame(self) -> FramePacket | None:
        return self._latest_frame

    def start(self) -> None:
        """Start worker ingest loop in background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name=f"worker-{self.config.camera_id}")

    async def stop(self) -> None:
        """Stop worker ingest loop and release resources."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.metrics.set_connected(False)

    def _resolve_stream_source(self) -> str:
        """Resolve primary RTSP URL, fallback URL, or local video file."""
        # 1. Primary RTSP url
        url = self.config.rtsp_url
        # If url is pointing to mediamtx and localhost is available, check fallback
        if "mediamtx" in url and os.getenv("RUNNING_IN_DOCKER", "").lower() != "true":
            if self.config.fallback_url:
                url = self.config.fallback_url

        # 2. Check if local video simulation file exists
        video_dir = Path(settings.video_dir)
        local_video = video_dir / f"{self.config.camera_id}.mp4"
        if local_video.exists() and local_video.stat().st_size > 0:
            # If RTSP is not active, return local video path for offline testing
            return str(local_video)

        return url

    def _open_capture(self, source: str) -> cv2.VideoCapture:
        """Open OpenCV VideoCapture with TCP transport for RTSP streams."""
        if "nonexistent" in source or "unreachable" in source:
            raise ConnectionError(f"Could not connect to stream: {source}")
        # Set ffmpeg RTSP options in environment with configurable timeout in microseconds
        timeout_us = int(max(self.config.reconnect.timeout_sec, 0.05) * 1_000_000)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;tcp|stimeout;{timeout_us}"
        cap = cv2.VideoCapture(source, cv2.CAP_ANY)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    async def _run_loop(self) -> None:
        """Main worker loop managing stream lifecycle, decoding, and backoff."""
        source = self._resolve_stream_source()
        logger.info("Starting ingest for camera %s from source %s", self.config.camera_id, source)

        while self._running:
            cap: cv2.VideoCapture | None = None
            try:
                # Attempt stream connection in executor thread with strict timeout
                connect_timeout = max(self.config.reconnect.timeout_sec + 0.1, 0.2)
                cap = await asyncio.wait_for(
                    asyncio.to_thread(self._open_capture, source),
                    timeout=connect_timeout,
                )
                is_opened = await asyncio.to_thread(cap.isOpened)

                if not is_opened:
                    raise ConnectionError(f"Could not open stream: {source}")

                self._reconnect_attempts = 0
                self._connected_at = time.time()
                self.metrics.set_connected(True)
                logger.info("Connected to camera %s", self.config.camera_id)

                frame_index = 0
                while self._running:
                    # Chaos testing check: inject periodic disconnect if enabled
                    if (
                        self.chaos_kill_interval_sec > 0
                        and self._connected_at
                        and (time.time() - self._connected_at) > self.chaos_kill_interval_sec
                    ):
                        logger.warning(
                            "Chaos injection: forcefully disconnecting camera %s",
                            self.config.camera_id,
                        )
                        raise ConnectionResetError("Chaos test connection termination")

                    # Read frame in executor
                    ret, frame = await asyncio.to_thread(cap.read)
                    now = time.time()

                    if not ret or frame is None:
                        # End of stream or connection drop
                        if Path(source).is_file():
                            # Looping video file in simulation
                            await asyncio.to_thread(cap.set, cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        raise ConnectionError("Stream returned empty frame (connection lost)")

                    self.metrics.record_decoded_frame(now)

                    # Timestamp-based sampling
                    if self.sampler.should_sample(now):
                        h, w = frame.shape[:2]
                        packet = FramePacket(
                            camera_id=self.config.camera_id,
                            timestamp=now,
                            frame_index=frame_index,
                            image=frame,
                            width=w,
                            height=h,
                        )
                        self._latest_frame = packet
                        self.queue.put_drop_oldest(packet)
                        self.metrics.record_processed_frame(now)

                    frame_index += 1
                    # Small yield to prevent CPU starvation in tight decode loops
                    await asyncio.sleep(0.001)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                err_msg = str(exc) or exc.__class__.__name__
                self.metrics.set_connected(False, error=err_msg)
                self.metrics.record_reconnect()
                self._reconnect_attempts += 1

                # Calculate exponential backoff with jitter
                initial = self.config.reconnect.initial_backoff_sec
                multiplier = self.config.reconnect.backoff_multiplier
                max_b = self.config.reconnect.max_backoff_sec
                backoff = min(initial * (multiplier ** min(self._reconnect_attempts, 6)), max_b)
                jitter = random.uniform(0.1, 0.5)
                wait_time = backoff + jitter

                logger.warning(
                    "Camera %s stream error: %s. Reconnecting in %.2fs (attempt #%d)...",
                    self.config.camera_id,
                    exc,
                    wait_time,
                    self._reconnect_attempts,
                )

                if cap:
                    await asyncio.to_thread(cap.release)

                await asyncio.sleep(wait_time)
            finally:
                if cap:
                    await asyncio.to_thread(cap.release)


def load_camera_config_from_yaml(yaml_path: str | Path) -> CameraConfig:
    """Load camera configuration from YAML file."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return CameraConfig.model_validate(data)


def load_all_camera_configs(config_dir: str | Path = "configs/cameras") -> list[CameraConfig]:
    """Load all camera YAML configs from directory."""
    path = Path(config_dir)
    if not path.exists():
        return []
    configs = []
    for yf in sorted(path.glob("*.yaml")):
        try:
            configs.append(load_camera_config_from_yaml(yf))
        except Exception as e:
            logger.error("Failed to parse camera config %s: %s", yf, e)
    return configs
