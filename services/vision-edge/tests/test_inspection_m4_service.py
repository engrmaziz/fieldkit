"""Tests for Project 6 M4: Live Inspection Service, Heatmap Storage, and Telemetry."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient
from fieldkit_vision.inspect.decision import DecisionAction
from fieldkit_vision.inspect.models import (
    InspectionResponse,
)
from fieldkit_vision.inspect.storage import HeatmapStorageManager
from fieldkit_vision.inspect.worker import InspectionWorker
from fieldkit_vision.main import app


def test_heatmap_storage_manager(tmp_path: Path) -> None:
    """Test HeatmapStorageManager stores JPEG heatmaps locally and generates valid URIs."""
    storage = HeatmapStorageManager(local_dir=tmp_path / "heatmaps")

    # Generate dummy heatmap and image
    img = np.ones((256, 256, 3), dtype=np.uint8) * 128
    heatmap = np.zeros((256, 256), dtype=np.float32)
    heatmap[100:150, 100:150] = 0.95

    uri, local_path = storage.save_heatmap_overlay(
        product_id="metal_nut",
        inspection_id="test_insp_001",
        image=img,
        heatmap=heatmap,
    )

    assert "test_insp_001" in uri
    assert Path(local_path).exists()
    assert Path(local_path).stat().st_size > 0

    # Verify saved image is valid JPEG
    read_img = cv2.imread(str(local_path))
    assert read_img is not None
    assert read_img.shape == (256, 256, 3)


def test_inspection_worker_end_to_end(tmp_path: Path) -> None:
    """Verify InspectionWorker loads configs, runs inference, and records dispositions."""
    storage = HeatmapStorageManager(local_dir=tmp_path / "worker_heatmaps")
    worker = InspectionWorker(storage_manager=storage)

    # 1. Clean steel sheet part
    clean_img = np.ones((256, 256, 3), dtype=np.uint8) * 135
    for y in range(0, 256, 4):
        cv2.line(clean_img, (0, y), (256, y), (140, 140, 140), 1)

    _, encoded_clean = cv2.imencode(".png", clean_img)

    resp_clean = worker.inspect_image(
        product_id="steel_sheet",
        image_bytes=encoded_clean.tobytes(),
        part_id="part_clean_001",
    )

    assert isinstance(resp_clean, InspectionResponse)
    assert resp_clean.disposition in (DecisionAction.PASS, DecisionAction.REVIEW)
    assert resp_clean.latency_ms < 100.0
    assert resp_clean.part_id == "part_clean_001"

    # 2. Defective part
    def_img = np.copy(clean_img)
    cv2.rectangle(def_img, (20, 100), (236, 140), (40, 40, 40), -1)  # rolled-in scale
    _, encoded_def = cv2.imencode(".png", def_img)

    resp_def = worker.inspect_image(
        product_id="steel_sheet",
        image_bytes=encoded_def.tobytes(),
        part_id="part_def_002",
    )

    assert resp_def.disposition == DecisionAction.REJECT
    assert resp_def.heatmap_url is not None
    assert resp_def.anomaly_score > 0.35


def test_inspection_api_endpoints() -> None:
    """Verify FastAPI /inspect endpoints for real-time inference and history queries."""
    client = TestClient(app)

    # 1. Test GET /inspect/products
    res_prod = client.get("/inspect/products")
    assert res_prod.status_code == 200
    products = res_prod.json()
    assert "steel_sheet" in products or "metal_nut" in products

    # 2. Test POST /inspect/steel_sheet
    dummy_img = np.ones((256, 256, 3), dtype=np.uint8) * 130
    _, img_buf = cv2.imencode(".jpg", dummy_img)

    files = {"file": ("component.jpg", img_buf.tobytes(), "image/jpeg")}
    data = {"part_id": "api_part_test_101"}

    res_post = client.post("/inspect/steel_sheet", files=files, data=data)
    assert res_post.status_code == 200
    res_data = res_post.json()
    assert res_data["part_id"] == "api_part_test_101"
    assert "disposition" in res_data
    assert "anomaly_score" in res_data

    inspection_id = res_data["inspection_id"]

    # 3. Test GET /inspect/records
    res_records = client.get("/inspect/records?product_id=steel_sheet&limit=10")
    assert res_records.status_code == 200
    records = res_records.json()
    assert len(records) >= 1
    assert any(r["inspection_id"] == inspection_id for r in records)

    # 4. Test GET /inspect/records/{inspection_id}
    res_single = client.get(f"/inspect/records/{inspection_id}")
    assert res_single.status_code == 200
    assert res_single.json()["inspection_id"] == inspection_id

    # 5. Test GET /inspect/heatmap/{inspection_id}
    res_hm = client.get(f"/inspect/heatmap/{inspection_id}")
    assert res_hm.status_code == 200
    assert res_hm.headers["content-type"] == "image/jpeg"
    assert len(res_hm.content) > 0

    # 6. Test POST /inspect/records/{inspection_id}/review (operator triage)
    review_payload = {
        "operator_label": "rolled_in_scale",
        "operator_notes": "Confirmed defect by Hamburg Plant QA shift 1",
        "reviewed_by": "mehmet.yilmaz",
    }
    res_rev = client.post(f"/inspect/records/{inspection_id}/review", json=review_payload)
    assert res_rev.status_code == 200
    rev_data = res_rev.json()
    assert rev_data["operator_label"] == "rolled_in_scale"
    assert rev_data["reviewed_by"] == "mehmet.yilmaz"
    assert rev_data["reviewed_at"] is not None


def test_conveyor_load_benchmark_service(tmp_path: Path) -> None:
    """Verify sustained conveyor line inspection under simulated multi-product load."""
    from evals.p6.load_test_inspection import run_conveyor_load_benchmark

    result = run_conveyor_load_benchmark(num_items=25, storage_dir=tmp_path / "conv_heatmaps")
    assert result.total_inspections == 25
    assert result.all_targets_met is True
    assert result.latency_target_passed is True  # P95 < 100 ms
    assert result.throughput_target_passed is True  # > 15 FPS
    assert result.p95_latency_ms < 100.0

