"""Unit test suite for Project 6 M5: Review Queue, Manifests, Retraining, Shadow Mode, and Drift."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient
from fieldkit_mlops.drift import ScoreDriftMonitor, calculate_psi
from fieldkit_mlops.manifest import DatasetManifest, ManifestItem, SplitType
from fieldkit_mlops.registry import ModelRegistry, ModelStage
from fieldkit_mlops.retrain import execute_retrain_pipeline
from fieldkit_vision.inspect.models import InspectionRecord
from fieldkit_vision.inspect.shadow import ShadowInspectionManager
from fieldkit_vision.main import app


def test_psi_drift_calculation_and_alerting() -> None:
    """Verify Population Stability Index accurately distinguishes stable vs drifted distributions."""
    rng = np.random.RandomState(42)

    # Reference distribution (normal component inspection scores: mean=0.18, std=0.04)
    ref_scores = rng.normal(0.18, 0.04, 200).clip(0.01, 0.50)

    # 1. Stable sample drawn from identical underlying distribution
    stable_scores = rng.normal(0.18, 0.04, 150).clip(0.01, 0.50)
    psi_stable = calculate_psi(ref_scores, stable_scores)
    assert psi_stable < 0.10, f"Expected stable PSI < 0.10, got {psi_stable:.4f}"

    # 2. Drifted sample (e.g. novel supplier material shift: mean=0.38, std=0.08)
    drifted_scores = rng.normal(0.38, 0.08, 150).clip(0.05, 0.90)
    psi_drifted = calculate_psi(ref_scores, drifted_scores)
    assert psi_drifted > 0.20, f"Expected critical drift PSI > 0.20, got {psi_drifted:.4f}"

    # 3. Test ScoreDriftMonitor integration
    monitor = ScoreDriftMonitor(critical_threshold=0.20)
    monitor.set_reference_scores("metal_nut", ref_scores)

    for score in stable_scores[:60]:
        monitor.record_score("metal_nut", float(score))

    analysis_stable = monitor.analyze_drift("metal_nut", min_samples=25)
    assert analysis_stable.status == "STABLE"
    assert not analysis_stable.drift_detected

    # Record drifted stream
    monitor_drifted = ScoreDriftMonitor(critical_threshold=0.20)
    monitor_drifted.set_reference_scores("metal_nut", ref_scores)
    for score in drifted_scores[:60]:
        monitor_drifted.record_score("metal_nut", float(score))

    analysis_drifted = monitor_drifted.analyze_drift("metal_nut", min_samples=25)
    assert analysis_drifted.status == "CRITICAL"
    assert analysis_drifted.drift_detected is True
    assert "CRITICAL distribution drift detected" in (analysis_drifted.alert_message or "")


def test_dataset_manifest_and_frozen_test_isolation(tmp_path: Path) -> None:
    """Verify manifest versions, content hashing, and immutable frozen test set."""
    manifest = DatasetManifest(dataset_name="metal_nut", version="v1.0.0")

    # Add frozen test items
    for i in range(10):
        manifest.add_item(
            ManifestItem(
                item_id=f"test_item_{i}",
                relative_path=f"test/{i}.png",
                sha256=f"hash_test_{i}",
                dhash=1000 + i,
                label="good" if i < 8 else "scratch",
                is_anomaly=(i >= 8),
                split=SplitType.TEST,
                product_id="metal_nut",
            )
        )

    # Add training items
    for i in range(15):
        manifest.add_item(
            ManifestItem(
                item_id=f"train_item_{i}",
                relative_path=f"train/{i}.png",
                sha256=f"hash_train_{i}",
                dhash=2000 + i,
                label="good",
                is_anomaly=False,
                split=SplitType.TRAIN,
                product_id="metal_nut",
            )
        )

    # Save and reload
    save_path = tmp_path / "manifest.json"
    manifest.save(save_path)
    loaded = DatasetManifest.load(save_path)

    assert len(loaded.items) == 25
    assert len(loaded.get_split(SplitType.TEST)) == 10
    assert len(loaded.get_split(SplitType.TRAIN)) == 15

    # Test that adding review items only touches TRAIN / RECENT_EVAL
    loaded.add_item(
        ManifestItem(
            item_id="reviewed_item_001",
            relative_path="reviewed/001.png",
            sha256="hash_rev_001",
            dhash=3001,
            label="rolled_in_scale",
            is_anomaly=True,
            split=SplitType.TRAIN,
            product_id="metal_nut",
        )
    )
    # Frozen test set remains strictly immutable
    assert len(loaded.get_split(SplitType.TEST)) == 10
    assert len(loaded.get_split(SplitType.TRAIN)) == 16


def test_closed_retraining_and_candidate_registration(tmp_path: Path) -> None:
    """Verify retraining loop evaluates candidate and registers in ModelRegistry."""
    registry = ModelRegistry(registry_root=tmp_path / "registry")
    manifest = DatasetManifest(dataset_name="metal_nut", version="v1.0.0")

    # Populate train items
    for i in range(8):
        manifest.add_item(
            ManifestItem(
                item_id=f"train_{i}",
                relative_path=f"train/{i}.png",
                sha256=f"sha_{i}",
                dhash=100 + i,
                label="good",
                is_anomaly=False,
                split=SplitType.TRAIN,
                product_id="metal_nut",
            )
        )

    # Populate frozen test items
    for i in range(10):
        manifest.add_item(
            ManifestItem(
                item_id=f"test_{i}",
                relative_path=f"test/{i}.png",
                sha256=f"sha_t_{i}",
                dhash=500 + i,
                label="good" if i < 7 else "scratches",
                is_anomaly=(i >= 7),
                split=SplitType.TEST,
                product_id="metal_nut",
            )
        )

    result = execute_retrain_pipeline(
        product_id="metal_nut",
        manifest=manifest,
        registry=registry,
        candidate_version="cand_test_01",
        output_dir=tmp_path / "candidates",
    )

    assert result.product_id == "metal_nut"
    assert result.candidate_version == "cand_test_01"
    assert result.gate_passed is True
    assert result.registered is True
    assert Path(result.artifact_path).exists()

    # Check candidate in registry
    cand_models = [m for m in registry.list_models("metal_nut") if m.stage == ModelStage.CANDIDATE]
    assert len(cand_models) >= 1
    assert cand_models[-1].version == "cand_test_01"


def test_shadow_execution_manager_and_promotion_report(tmp_path: Path) -> None:
    """Verify shadow execution evaluates candidate without impacting live decision."""
    registry = ModelRegistry(registry_root=tmp_path / "registry")
    # Register candidate
    registry.register_model(
        model_name="metal_nut",
        version="cand_v2.0.0",
        artifact_path="data/cand.npz",
        stage=ModelStage.CANDIDATE,
    )
    # Register production
    registry.register_model(
        model_name="metal_nut",
        version="prod_v1.0.0",
        artifact_path="data/prod.npz",
        stage=ModelStage.PRODUCTION,
    )

    shadow_mgr = ShadowInspectionManager(registry=registry)
    assert shadow_mgr.has_candidate("metal_nut") is True

    dummy_img = np.ones((256, 256, 3), dtype=np.uint8) * 128

    # Simulate 15 live records
    from datetime import UTC, datetime
    records = []
    for i in range(15):
        rec = InspectionRecord(
            inspection_id=f"insp_shadow_{i}",
            product_id="metal_nut",
            part_id=f"part_{i}",
            plant_id="DE-HAM",
            timestamp=datetime.now(UTC),
            disposition="pass" if i < 11 else "reject",
            disposition_reason="verified_clean" if i < 11 else "confirmed_defect",
            anomaly_score=0.15 if i < 11 else 0.72,
            defect_class="good" if i < 11 else "scratches",
            defect_confidence=0.98,
            is_audit_sample=False,
            latency_ms=15.0,
        )
        records.append(rec)
        paired = shadow_mgr.record_shadow_execution("metal_nut", rec, dummy_img)
        assert paired is not None
        assert paired.candidate_version == "cand_v2.0.0"

    report = shadow_mgr.generate_promotion_report("metal_nut", min_samples=10)
    assert report.total_shadow_samples == 15
    assert report.agreement_rate >= 0.85
    assert report.candidate_p95_latency_ms < 100.0
    assert report.promotion_recommended is True


def test_model_promotion_and_instant_rollback(tmp_path: Path) -> None:
    """Verify promotion from candidate to production and instant rollback."""
    registry = ModelRegistry(registry_root=tmp_path / "registry")
    registry.register_model(
        model_name="metal_nut",
        version="v1.0.0",
        artifact_path="data/v1.npz",
        stage=ModelStage.PRODUCTION,
    )
    registry.register_model(
        model_name="metal_nut",
        version="cand_v2.0.0",
        artifact_path="data/v2.npz",
        stage=ModelStage.CANDIDATE,
    )

    # 1. Promote candidate
    promoted = registry.promote_candidate(
        model_name="metal_nut",
        version="cand_v2.0.0",
        promoted_by="mehmet.yilmaz",
        notes="High agreement in shadow run",
    )
    assert promoted is True

    prod = registry.get_production_model("metal_nut")
    assert prod is not None
    assert prod.version == "cand_v2.0.0"
    assert prod.stage == ModelStage.PRODUCTION

    # 2. Instant rollback to v1.0.0
    rolled_back = registry.rollback_to_version("metal_nut", "v1.0.0")
    assert rolled_back is True

    current_prod = registry.get_production_model("metal_nut")
    assert current_prod is not None
    assert current_prod.version == "v1.0.0"


def test_fastapi_m5_endpoints(tmp_path: Path) -> None:
    """Verify FastAPI endpoints for review queue, retraining, shadow report, promotion, and drift."""
    client = TestClient(app)

    # 1. Ingest a part that goes to review queue or submit an inspection
    dummy_img = np.ones((256, 256, 3), dtype=np.uint8) * 128
    # Add scratch to trigger review/reject
    cv2.line(dummy_img, (50, 50), (200, 200), (20, 20, 20), 2)
    _, buf = cv2.imencode(".jpg", dummy_img)

    files = {"file": ("part.jpg", buf.tobytes(), "image/jpeg")}
    data = {"part_id": "m5_test_part_001"}
    res_post = client.post("/inspect/metal_nut", files=files, data=data)
    assert res_post.status_code == 200
    insp_id = res_post.json()["inspection_id"]

    # 2. Test GET /inspect/review-queue
    res_queue = client.get("/inspect/review-queue?product_id=metal_nut")
    assert res_queue.status_code == 200
    assert isinstance(res_queue.json(), list)

    # 3. Test POST /inspect/reviews
    review_body = {
        "inspection_id": insp_id,
        "verdict": "defect",
        "defect_class": "scratches",
        "polygon": [[50.0, 50.0], [200.0, 200.0]],
        "notes": "Surface scratch verified by Mehmet",
        "reviewed_by": "mehmet.yilmaz",
    }
    res_rev = client.post("/inspect/reviews", json=review_body)
    assert res_rev.status_code == 200
    assert res_rev.json()["operator_label"] == "scratches"
    assert res_rev.json()["reviewed_by"] == "mehmet.yilmaz"

    # 4. Test POST /inspect/retrain
    res_retrain = client.post("/inspect/retrain", json={"product_id": "metal_nut"})
    assert res_retrain.status_code == 200
    retrain_data = res_retrain.json()
    assert retrain_data["status"] == "SUCCESS"
    assert retrain_data["gate_passed"] is True
    cand_ver = retrain_data["candidate_version"]

    # 5. Ingest parts to accumulate shadow executions
    for i in range(12):
        files_shadow = {"file": ("part.jpg", buf.tobytes(), "image/jpeg")}
        client.post("/inspect/metal_nut", files=files_shadow, data={"part_id": f"part_sh_{i}"})

    # 6. Test GET /inspect/shadow/report
    res_shadow = client.get("/inspect/shadow/report?product_id=metal_nut")
    assert res_shadow.status_code == 200
    shadow_data = res_shadow.json()
    assert shadow_data["product_id"] == "metal_nut"
    assert shadow_data["total_shadow_samples"] >= 12
    assert "agreement_rate" in shadow_data

    # 7. Test GET /inspect/shadow/records
    res_sh_recs = client.get("/inspect/shadow/records?product_id=metal_nut&limit=10")
    assert res_sh_recs.status_code == 200
    assert len(res_sh_recs.json()) >= 1

    # 8. Test POST /inspect/models/promote
    promote_body = {
        "product_id": "metal_nut",
        "version": cand_ver,
        "promoted_by": "mehmet.yilmaz",
        "role": "quality",
        "notes": "Approved after shadow validation",
    }
    res_promote = client.post("/inspect/models/promote", json=promote_body)
    assert res_promote.status_code == 200
    assert res_promote.json()["status"] == "PROMOTED"

    # 9. Test POST /inspect/models/rollback
    rollback_body = {
        "product_id": "metal_nut",
        "target_version": "v1.0.0",
    }
    res_rollback = client.post("/inspect/models/rollback", json=rollback_body)
    assert res_rollback.status_code == 200
    assert res_rollback.json()["status"] == "ROLLED_BACK"

    # 10. Test GET /inspect/models
    res_models = client.get("/inspect/models?product_id=metal_nut")
    assert res_models.status_code == 200
    assert len(res_models.json()) >= 2

    # 11. Test GET /inspect/drift
    res_drift = client.get("/inspect/drift?product_id=metal_nut")
    assert res_drift.status_code == 200
    drift_data = res_drift.json()
    assert drift_data["product_id"] == "metal_nut"
    assert "psi" in drift_data
    assert "status" in drift_data
