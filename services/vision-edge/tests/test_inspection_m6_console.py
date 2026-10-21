"""Integration tests for InspectAI Web Console UI (Milestone 6).

Verifies that the backend endpoints powering the Next.js 14 operator console
(/inspection) return expected schemas, support adjudication, shadow telemetry,
model lifecycle, and heatmap binary streaming.
"""

from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient
from fieldkit_vision.main import app


def test_console_catalog_and_inspection_flow() -> None:
    """Verify console product catalog and multipart image inspection."""
    client = TestClient(app)

    # 1. Product Catalog
    res_prod = client.get("/inspect/products")
    assert res_prod.status_code == 200
    products = res_prod.json()
    assert isinstance(products, list)
    assert "metal_nut" in products
    assert "steel_sheet" in products

    # 2. Ingest part on conveyor
    sample = np.ones((256, 256, 3), dtype=np.uint8) * 160
    cv2.circle(sample, (128, 128), 30, (30, 30, 30), -1)
    _, buf = cv2.imencode(".jpg", sample)

    files = {"file": ("conveyor_sample.jpg", buf.tobytes(), "image/jpeg")}
    res_insp = client.post("/inspect/steel_sheet", files=files, data={"part_id": "console_part_101"})
    assert res_insp.status_code == 200
    insp_data = res_insp.json()
    insp_id = insp_data["inspection_id"]
    assert insp_data["product_id"] == "steel_sheet"
    assert insp_data["disposition"].upper() in ["PASS", "REVIEW", "REJECT"]
    assert "anomaly_score" in insp_data
    assert "defect_class" in insp_data
    assert "latency_ms" in insp_data

    # 3. Fetch inspection records for console live grid
    res_recs = client.get("/inspect/records?product_id=steel_sheet&limit=20")
    assert res_recs.status_code == 200
    records = res_recs.json()
    assert isinstance(records, list)
    matching = [r for r in records if r["inspection_id"] == insp_id]
    assert len(matching) == 1

    # 4. Fetch binary heatmap overlay for opacity slider
    res_hm = client.get(f"/inspect/heatmap/{insp_id}")
    assert res_hm.status_code == 200
    assert res_hm.headers["content-type"] == "image/jpeg"
    assert len(res_hm.content) > 100


def test_console_review_adjudication_flow() -> None:
    """Verify operator review queue and keyboard-assisted adjudication."""
    client = TestClient(app)

    # Ingest a sample with visible defect
    sample = np.ones((256, 256, 3), dtype=np.uint8) * 140
    cv2.line(sample, (40, 40), (220, 220), (10, 10, 10), 3)
    _, buf = cv2.imencode(".jpg", sample)

    files = {"file": ("defect_part.jpg", buf.tobytes(), "image/jpeg")}
    res_insp = client.post("/inspect/steel_sheet", files=files, data={"part_id": "console_queue_001"})
    assert res_insp.status_code == 200
    insp_id = res_insp.json()["inspection_id"]

    # Operator loads review queue
    res_queue = client.get("/inspect/review-queue?product_id=steel_sheet")
    assert res_queue.status_code == 200
    queue = res_queue.json()
    assert isinstance(queue, list)

    # Operator adjudicates via [R] Reject or [P] Pass with notes and polygon
    review_submission = {
        "inspection_id": insp_id,
        "verdict": "defect",
        "defect_class": "scratches",
        "polygon": [[40.0, 40.0], [220.0, 220.0]],
        "notes": "Longitudinal handling scratch confirmed by Mehmet Yilmaz",
        "reviewed_by": "M. Yilmaz (Quality Lead)",
    }
    res_adjudicate = client.post("/inspect/reviews", json=review_submission)
    assert res_adjudicate.status_code == 200
    adjudicated = res_adjudicate.json()
    assert adjudicated["operator_label"] == "scratches"
    assert adjudicated["reviewed_by"] == "M. Yilmaz (Quality Lead)"
    assert "scratch confirmed" in adjudicated["operator_notes"]
    assert adjudicated["reviewed_at"] is not None


def test_console_model_promotion_and_drift_flow() -> None:
    """Verify model promotion, shadow telemetry, rollback, and drift monitoring."""
    client = TestClient(app)

    # 1. Trigger candidate retraining from console
    res_retrain = client.post("/inspect/retrain", json={"product_id": "steel_sheet"})
    assert res_retrain.status_code == 200
    retrain_data = res_retrain.json()
    assert retrain_data["status"] == "SUCCESS"
    cand_version = retrain_data["candidate_version"]

    # 2. Query model catalog for console comparison view
    res_models = client.get("/inspect/models?product_id=steel_sheet")
    assert res_models.status_code == 200
    models_list = res_models.json()
    assert isinstance(models_list, list)
    assert len(models_list) >= 1
    versions = [m["version"] for m in models_list]
    assert "v1.0.0" in versions

    # 3. Query shadow mode telemetry report
    res_shadow = client.get("/inspect/shadow/report?product_id=steel_sheet")
    assert res_shadow.status_code == 200
    sh_rep = res_shadow.json()
    assert sh_rep["product_id"] == "steel_sheet"
    assert "agreement_rate" in sh_rep

    # 4. Promote candidate model
    promote_req = {
        "product_id": "steel_sheet",
        "version": cand_version,
        "promoted_by": "M. Yilmaz",
        "role": "quality",
        "notes": "Candidate passed frozen benchmark gates with 0 escapes and 100% agreement",
    }
    res_promote = client.post("/inspect/models/promote", json=promote_req)
    assert res_promote.status_code == 200
    assert res_promote.json()["status"] == "PROMOTED"

    # 5. Instant rollback to previous production version
    rollback_req = {
        "product_id": "steel_sheet",
        "target_version": "v1.0.0",
    }
    res_rollback = client.post("/inspect/models/rollback", json=rollback_req)
    assert res_rollback.status_code == 200
    assert res_rollback.json()["status"] == "ROLLED_BACK"

    # 6. Query PSI distribution drift indicators
    res_drift = client.get("/inspect/drift?product_id=steel_sheet")
    assert res_drift.status_code == 200
    drift_data = res_drift.json()
    assert drift_data["product_id"] == "steel_sheet"
    assert "psi" in drift_data
    assert "drift_detected" in drift_data
