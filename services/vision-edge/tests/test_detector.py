"""Unit tests for YOLO ONNX detector, letterboxing, NMS, and batching."""

import numpy as np
from fieldkit_vision.detector import (
    Detection,
    YOLOOnnxDetector,
    apply_nms,
    letterbox,
    scale_boxes,
)


def test_detection_properties() -> None:
    """Verify Detection helper properties: head_region and foot_point."""
    det = Detection(
        box=[100.0, 200.0, 300.0, 600.0],  # w=200, h=400
        class_id=0,
        class_name="person",
        confidence=0.95,
    )
    assert det.width == 200.0
    assert det.height == 400.0
    # Head region is top 25% of height (400 * 0.25 = 100 -> y1=200, y2=300)
    assert det.head_region == [100.0, 200.0, 300.0, 300.0]
    # Foot point is bottom center: x=(100+300)/2=200, y=600
    assert det.foot_point == (200.0, 600.0)


def test_letterbox_padding() -> None:
    """Verify letterbox scales preserving aspect ratio with symmetric gray padding."""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    padded, r, (dw, dh) = letterbox(img, (640, 640))

    # Padded image must be exactly (640, 640, 3)
    assert padded.shape == (640, 640, 3)
    # 1920 -> 640 is ratio 0.3333...
    assert round(r, 4) == round(640 / 1920, 4)
    # Height unpadded = 1080 * (640/1920) = 360; padding dh = (640-360)/2 = 140
    assert dh == 140.0
    assert dw == 0.0


def test_scale_boxes_inversion() -> None:
    """Verify scale_boxes maps letterbox coordinates back to original image dimensions."""
    orig_shape = (1080, 1920)
    img = np.zeros((orig_shape[0], orig_shape[1], 3), dtype=np.uint8)
    _, r, padding = letterbox(img, (640, 640))

    # Box inside the unpadded 640x360 region
    # Center box: x1=100, y1=dh+50=190, x2=500, y2=dh+250=390
    boxes = np.array([[100.0, 190.0, 500.0, 390.0]])
    scaled = scale_boxes(boxes, r, padding, orig_shape)

    assert scaled.shape == (1, 4)
    # x should scale by 1920/640 = 3.0 -> 300 to 1500
    assert round(scaled[0][0]) == 300
    assert round(scaled[0][2]) == 1500
    # y should subtract dh=140, then multiply by 3.0 -> (190-140)*3 = 150, (390-140)*3 = 750
    assert round(scaled[0][1]) == 150
    assert round(scaled[0][3]) == 750


def test_apply_nms() -> None:
    """Verify that redundant overlapping boxes are suppressed by NMS."""
    # Two almost identical boxes
    boxes = np.array([
        [100.0, 100.0, 200.0, 200.0],
        [102.0, 101.0, 201.0, 202.0],
        [400.0, 400.0, 500.0, 500.0],  # Separate box
    ])
    scores = np.array([0.90, 0.85, 0.95])

    keep = apply_nms(boxes, scores, score_threshold=0.5, iou_threshold=0.45)
    # First two overlap heavily; only the higher score (index 0) and the separate box (index 2) should remain
    assert len(keep) == 2
    assert 2 in keep
    assert 0 in keep
    assert 1 not in keep


def test_yolo_detector_batch_and_benchmark() -> None:
    """Verify detector single and batch inference and benchmark output."""
    detector = YOLOOnnxDetector(model_path=None)
    assert detector.is_simulated is True

    frame = np.full((360, 640, 3), 100, dtype=np.uint8)

    # Single detect
    dets = detector.detect(frame)
    assert len(dets) >= 3
    classes = [d.class_name for d in dets]
    assert "person" in classes
    assert "helmet" in classes
    assert "forklift" in classes

    # Batch detect
    batch_dets = detector.detect_batch([frame, frame, frame, frame])
    assert len(batch_dets) == 4
    for cam_dets in batch_dets:
        assert len(cam_dets) >= 3

    # Benchmark
    bench = detector.benchmark(num_frames=20, batch_size=4)
    assert bench["batch_size"] == 4.0
    assert bench["fps"] > 0
    assert bench["ms_per_frame"] > 0
