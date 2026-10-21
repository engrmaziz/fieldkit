"""Unit tests for fieldkit-mlops: manifests, evaluation metrics, and model registry."""

from __future__ import annotations

import tempfile

import numpy as np
from fieldkit_mlops.evaluate import (
    compute_calibration_error,
    compute_classification_metrics,
    compute_image_auroc,
    compute_pixel_auroc,
    compute_pro_score,
)
from fieldkit_mlops.manifest import (
    DatasetManifest,
    ManifestItem,
    SplitType,
    compute_dhash,
    compute_sha256,
    hamming_distance,
)
from fieldkit_mlops.registry import ModelRegistry, ModelStage


def test_manifest_and_dhash_deduplication() -> None:
    # 1. Create synthetic images
    img1 = np.zeros((100, 100, 3), dtype=np.uint8)
    img1[20:50, 20:50] = 200

    # Near duplicate with minor noise
    img2 = img1.copy()
    img2[21:49, 21:49] = 198

    # Distinct image
    img3 = np.zeros((100, 100, 3), dtype=np.uint8)
    img3[70:90, 70:90] = 255

    dh1 = compute_dhash(img1)
    dh2 = compute_dhash(img2)
    dh3 = compute_dhash(img3)

    assert hamming_distance(dh1, dh2) <= 2
    assert hamming_distance(dh1, dh3) > 2

    # 2. Build Manifest
    manifest = DatasetManifest(dataset_name="mvtec_nut", version="1.0.0")
    manifest.add_item(
        ManifestItem(
            item_id="item_01",
            relative_path="train/01.png",
            sha256=compute_sha256(b"content_1"),
            dhash=dh1,
            label="good",
            is_anomaly=False,
            split=SplitType.TRAIN,
        )
    )
    manifest.add_item(
        ManifestItem(
            item_id="item_02",
            relative_path="test/02.png",
            sha256=compute_sha256(b"content_2"),
            dhash=dh2,  # near duplicate of item_01
            label="good",
            is_anomaly=False,
            split=SplitType.TEST,
        )
    )
    manifest.add_item(
        ManifestItem(
            item_id="item_03",
            relative_path="test/03.png",
            sha256=compute_sha256(b"content_3"),
            dhash=dh3,
            label="defect",
            is_anomaly=True,
            split=SplitType.TEST,
        )
    )

    cleaned_manifest, dropped = manifest.deduplicate_cross_splits(max_hamming_distance=2)
    assert dropped == 1
    assert len(cleaned_manifest.items) == 2
    assert cleaned_manifest.items[1].item_id == "item_03"

    # Test JSON round-trip
    json_str = cleaned_manifest.to_json()
    loaded = DatasetManifest.from_json(json_str)
    assert loaded.dataset_name == "mvtec_nut"
    assert len(loaded.items) == 2


def test_evaluation_metrics() -> None:
    # 1. Image AUROC
    y_true = [0, 0, 0, 1, 1, 1]
    y_score = [0.1, 0.2, 0.15, 0.8, 0.9, 0.85]
    auroc = compute_image_auroc(y_true, y_score)
    assert auroc == 1.0

    # 2. Pixel AUROC & PRO Score
    mask1 = np.zeros((32, 32), dtype=np.uint8)
    mask1[10:20, 10:20] = 1
    pred_heat1 = np.zeros((32, 32), dtype=np.float32)
    pred_heat1[10:20, 10:20] = 0.9
    pred_heat1[0:5, 0:5] = 0.1

    pix_auroc = compute_pixel_auroc([mask1], [pred_heat1])
    assert pix_auroc > 0.95

    pro = compute_pro_score([mask1], [pred_heat1])
    assert pro > 0.80

    # 3. Multi-Class Classification & ECE
    class_names = ["crazing", "inclusion", "good"]
    y_t = [0, 1, 2, 0, 1, 2]
    y_p = [0, 1, 2, 0, 1, 1]  # 5/6 correct
    report = compute_classification_metrics(y_t, y_p, class_names)
    assert report.accuracy > 0.80
    assert len(report.per_class) == 3

    probas = np.array([
        [0.9, 0.05, 0.05],
        [0.1, 0.8, 0.1],
        [0.05, 0.05, 0.9],
        [0.85, 0.1, 0.05],
        [0.15, 0.75, 0.1],
        [0.1, 0.7, 0.2],
    ])
    ece = compute_calibration_error(y_t, probas)
    assert 0.0 <= ece <= 0.3


def test_model_registry_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(registry_root=tmp_dir)

        # 1. Register Candidate Model
        c1 = registry.register_model(
            model_name="metal_nut_anomaly",
            version="v1.0.0-candidate",
            artifact_path="models/metal_nut_v1.onnx",
            stage=ModelStage.CANDIDATE,
            metrics={"image_auroc": 0.985},
        )
        assert c1.stage == ModelStage.CANDIDATE
        assert registry.get_production_model("metal_nut_anomaly") is None

        # 2. Promote Candidate to Production
        promoted = registry.promote_candidate("metal_nut_anomaly", "v1.0.0-candidate", promoted_by="mehmet")
        assert promoted is True
        prod = registry.get_production_model("metal_nut_anomaly")
        assert prod is not None
        assert prod.version == "v1.0.0-candidate"
        assert prod.promoted_by == "mehmet"

        # 3. Register v2 and Promote
        registry.register_model(
            model_name="metal_nut_anomaly",
            version="v2.0.0",
            artifact_path="models/metal_nut_v2.onnx",
            stage=ModelStage.CANDIDATE,
            metrics={"image_auroc": 0.992},
        )
        registry.promote_candidate("metal_nut_anomaly", "v2.0.0", promoted_by="mehmet")
        prod2 = registry.get_production_model("metal_nut_anomaly")
        assert prod2 is not None
        assert prod2.version == "v2.0.0"

        # 4. Rollback to v1.0.0-candidate
        rolled_back = registry.rollback_to_version("metal_nut_anomaly", "v1.0.0-candidate")
        assert rolled_back is True
        prod_rolled = registry.get_production_model("metal_nut_anomaly")
        assert prod_rolled is not None
        assert prod_rolled.version == "v1.0.0-candidate"
