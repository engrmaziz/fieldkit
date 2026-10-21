"""Unit tests for bounded queue backpressure and drop-oldest policy."""

import numpy as np
import pytest
from fieldkit_vision.camera_worker import BoundedFrameQueue
from fieldkit_vision.metrics import CameraMetricsTracker
from fieldkit_vision.models import FramePacket


def test_bounded_queue_drop_oldest() -> None:
    """Verify that bounded queue drops oldest frames under consumer backpressure."""
    tracker = CameraMetricsTracker(camera_id="cam_test")
    queue = BoundedFrameQueue(maxsize=4, metrics_tracker=tracker)

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

    # Push 10 frames without consuming
    for i in range(10):
        packet = FramePacket(
            camera_id="cam_test",
            timestamp=float(i),
            frame_index=i,
            image=dummy_img,
            width=100,
            height=100,
        )
        queue.put_drop_oldest(packet)

    # Verify queue size never exceeded 4
    assert queue.qsize() == 4
    # Verify 6 frames were dropped
    assert tracker.dropped_frames == 6

    # Verify remaining 4 frames are the NEWEST frames (indices 6, 7, 8, 9)
    remaining_indices = []
    while not queue.empty():
        pkt = queue.get_nowait()
        assert pkt is not None
        remaining_indices.append(pkt.frame_index)

    assert remaining_indices == [6, 7, 8, 9]


@pytest.mark.asyncio
async def test_bounded_queue_async_get() -> None:
    """Verify asynchronous frame retrieval."""
    queue = BoundedFrameQueue(maxsize=2)
    packet = FramePacket(
        camera_id="cam_async",
        timestamp=1.0,
        frame_index=1,
        image=np.zeros((10, 10, 3), dtype=np.uint8),
        width=10,
        height=10,
    )
    queue.put_drop_oldest(packet)
    retrieved = await queue.get()
    assert retrieved.frame_index == 1
    assert queue.empty()
