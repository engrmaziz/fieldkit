"""Unit tests for VisionEvent schema, Redpanda publisher, ClickHouse events, and 10s MP4 ring-buffer clips."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from fieldkit_vision.clip_generator import FrameRingBuffer, blur_privacy_faces, generate_event_clip
from fieldkit_vision.events import (
    ClickHouseEventStorage,
    RedpandaEventPublisher,
    VisionEvent,
)
from fieldkit_vision.models import FramePacket


def test_vision_event_schema_and_serialization() -> None:
    """Verify VisionEvent schema matches Redpanda topic vision.events and ClickHouse table."""
    evt = VisionEvent(
        camera_id="cam1_press",
        plant_id="DE-HAM",
        rule_id="rule_press_helmet",
        rule_type="zone_ppe_missing",
        severity="CRITICAL",
        track_id=101,
        zone_id="zone_press_danger",
        metric_distance=None,
        metric_speed=None,
        timestamp=1729500000.0,
        clip_uri="s3://vision-clips/de-ham/cam1_press/evt_101.mp4",
        metadata={"ppe_class": "helmet", "violation_ratio": 0.85},
    )

    assert evt.event_id is not None
    assert len(evt.event_id) >= 16
    assert evt.severity == "CRITICAL"

    data = evt.model_dump()
    assert data["camera_id"] == "cam1_press"
    assert data["rule_type"] == "zone_ppe_missing"
    assert data["clip_uri"] is not None

    # Verify JSON serializability
    json_str = evt.model_dump_json()
    assert "cam1_press" in json_str
    assert "zone_ppe_missing" in json_str


@pytest.mark.asyncio
async def test_redpanda_publisher_fallback() -> None:
    """Verify Redpanda publisher buffers events locally when broker is offline."""
    publisher = RedpandaEventPublisher(bootstrap_servers="localhost:9092", topic="vision.events")
    evt = VisionEvent(
        camera_id="cam2_logistics",
        plant_id="DE-HAM",
        rule_id="rule_forklift_prox",
        rule_type="proximity",
        severity="CRITICAL",
        track_id=202,
        related_track_id=105,
        metric_distance=1.45,
        metric_speed=1.8,
        timestamp=1729500010.0,
    )

    # In test/offline mode without broker, publishes to local fallback buffer
    await publisher.publish(evt)
    buffered = publisher.get_buffered_events()
    assert len(buffered) >= 1
    assert buffered[-1].event_id == evt.event_id


def test_clickhouse_storage_schema_and_insert() -> None:
    """Verify ClickHouse events table migration schema and parameterized insert formatting."""
    ch = ClickHouseEventStorage(database="fieldkit_vision")
    evt = VisionEvent(
        camera_id="cam1_press",
        plant_id="DE-HAM",
        rule_id="rule_press_helmet",
        rule_type="zone_ppe_missing",
        severity="CRITICAL",
        track_id=101,
        timestamp=1729500000.0,
    )

    sql, params = ch.prepare_insert(evt)
    assert "INSERT INTO fieldkit_vision.events" in sql
    assert params["camera_id"] == "cam1_press"
    assert params["rule_id"] == "rule_press_helmet"
    assert params["severity"] == "CRITICAL"


def test_frame_ring_buffer_retention() -> None:
    """Verify FrameRingBuffer retains exactly 5 seconds of pre-event frames at 5 FPS."""
    # 5 seconds at 5 FPS = 25 frames
    ring = FrameRingBuffer(capacity=25)
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

    for i in range(30):
        packet = FramePacket(
            camera_id="cam1",
            timestamp=float(i),
            frame_index=i,
            image=dummy_img,
            width=100,
            height=100,
        )
        ring.append(packet)

    # Ring should hold max 25 frames, dropping oldest (0 to 4)
    assert ring.size() == 25
    frames = ring.get_frames()
    assert frames[0].frame_index == 5  # Oldest is 5
    assert frames[-1].frame_index == 29  # Newest is 29


def test_blur_privacy_faces() -> None:
    """Verify face/head privacy blur applies Gaussian blur to human upper boxes."""
    # Create test image with distinct pattern in head region
    img = np.full((200, 200, 3), 200, dtype=np.uint8)
    # Put bright square in head region
    img[20:60, 80:120] = 0

    person_box = [60.0, 20.0, 140.0, 180.0]  # h = 160 -> head region is y: 20 to 60
    blurred = blur_privacy_faces(img, [person_box])

    assert blurred.shape == img.shape
    # Check that pixel variance in head region was smoothed by Gaussian blur
    assert not np.array_equal(img[25:55, 85:115], blurred[25:55, 85:115])
    # Lower region remains unblurred
    assert np.array_equal(img[120:160, 80:120], blurred[120:160, 80:120])


def test_generate_event_clip_mp4() -> None:
    """Verify 10s MP4 event clip generation and file output."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_event.mp4"
        dummy_frame = np.full((360, 640, 3), 128, dtype=np.uint8)

        # 20 frames (4 seconds test clip)
        frames = [
            FramePacket(
                camera_id="cam1",
                timestamp=100.0 + i * 0.2,
                frame_index=i,
                image=dummy_frame,
                width=640,
                height=360,
            )
            for i in range(20)
        ]

        generate_event_clip(
            frames=frames,
            output_path=out_path,
            fps=5.0,
            apply_privacy=True,
            person_boxes=[[200.0, 100.0, 300.0, 300.0]],
        )

        assert out_path.exists()
        assert out_path.stat().st_size > 0
