"""Unit tests for timestamp-based frame sampling."""

from fieldkit_vision.camera_worker import TimestampSampler


def test_timestamp_sampler_basic_downsampling() -> None:
    """Test downsampling a 25 FPS stream to 5 FPS strictly by timestamp."""
    sampler = TimestampSampler(target_fps=5.0)  # interval = 0.20s

    # Generate 50 frames at 25 FPS (0.04s interval, total 2.0 seconds)
    input_timestamps = [i * 0.04 for i in range(50)]
    sampled = [ts for ts in input_timestamps if sampler.should_sample(ts)]

    # In 2.0 seconds at 5 FPS, we expect exactly 10 or 11 frames (first frame at 0.0s + 10 intervals)
    assert len(sampled) in (10, 11)

    # Verify time delta between consecutive sampled frames is >= ~0.20s
    for i in range(len(sampled) - 1):
        dt = sampled[i + 1] - sampled[i]
        assert dt >= 0.19, f"Delta {dt} is too small for 5 FPS"


def test_timestamp_sampler_jitter_tolerance() -> None:
    """Test that minor packet jitter (e.g. 0.198s instead of 0.200s) does not drop a frame."""
    sampler = TimestampSampler(target_fps=5.0)

    assert sampler.should_sample(0.0) is True
    # 0.10s is too early
    assert sampler.should_sample(0.10) is False
    # 0.196s has 4ms jitter; should be accepted
    assert sampler.should_sample(0.196) is True
    # 0.25s is too early from 0.196s
    assert sampler.should_sample(0.25) is False
    # 0.395s (delta 0.199s) accepted
    assert sampler.should_sample(0.395) is True


def test_timestamp_sampler_loop_reset() -> None:
    """Test that looping video stream (timestamp jumps backwards) resets cleanly."""
    sampler = TimestampSampler(target_fps=5.0)

    assert sampler.should_sample(10.0) is True
    assert sampler.should_sample(10.2) is True
    # Video loops back to 0.0s
    assert sampler.should_sample(0.0) is True
    assert sampler.should_sample(0.2) is True
