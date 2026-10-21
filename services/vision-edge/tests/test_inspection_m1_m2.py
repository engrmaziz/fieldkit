"""Tests for Project 6 M1 (PatchCore Anomaly Baselines) and M2 (Supervised Defect Classifier)."""

from __future__ import annotations

import cv2
import numpy as np
from fieldkit_mlops.manifest import compute_dhash
from fieldkit_mlops.registry import ModelRegistry, ModelStage
from fieldkit_mlops.train_anomaly import greedy_k_center, train_patchcore_model
from fieldkit_vision.inspect.anomaly import PatchCoreAnomalyDetector
from fieldkit_vision.inspect.classifier import (
    DEFAULT_DEFECT_CLASSES,
    DefectClassifier,
)
from fieldkit_vision.inspect.preprocess import InspectionPreprocessor

from evals.p6.dataset import (
    _generate_synthetic_component_image,
)
from evals.p6.eval_anomaly import evaluate_anomaly_baselines
from evals.p6.eval_classifier import evaluate_defect_classifier


def test_inspection_preprocessor_roi_and_alignment() -> None:
    """Test ROI cropping and ORB homography reference alignment."""
    # Create test reference image
    ref_img = np.zeros((300, 300, 3), dtype=np.uint8)
    cv2.circle(ref_img, (150, 150), 50, (255, 255, 255), -1)
    cv2.rectangle(ref_img, (80, 80), (220, 220), (128, 128, 128), 2)

    preprocessor = InspectionPreprocessor(
        target_size=(256, 256),
        roi=[50, 50, 250, 250],
        alignment_enabled=True,
    )
    preprocessor.set_reference_image(ref_img)

    sample_img = np.copy(ref_img)
    res = preprocessor.preprocess(sample_img)

    assert res.image.shape == (256, 256, 3)
    assert res.image.dtype == np.uint8


def test_greedy_k_center_subsampling() -> None:
    """Test greedy k-Center algorithm selects diverse coreset centroids."""
    rng = np.random.RandomState(42)
    features = rng.normal(0, 1, (100, 12)).astype(np.float32)

    coreset = greedy_k_center(features, coreset_ratio=0.10)
    assert len(coreset) == 10
    assert coreset.shape[1] == 12


def test_patchcore_anomaly_detector_runtime() -> None:
    """Verify PatchCore inference returns valid scores, heatmaps, and overlays."""
    # Generate 3 normal test images
    normal_imgs = [
        _generate_synthetic_component_image("metal_nut", defect_type=None, seed=i)[0]
        for i in range(3)
    ]
    bundle = train_patchcore_model(normal_imgs, category="metal_nut", coreset_ratio=0.15)
    detector = PatchCoreAnomalyDetector(bundle=bundle, category="metal_nut", patch_size=16, stride=16)

    # Evaluate normal image
    normal_res = detector.predict(normal_imgs[0])
    assert 0.0 <= normal_res.anomaly_score <= 1.0
    assert normal_res.heatmap.shape == (256, 256)
    assert normal_res.inference_ms < 100.0
    assert not normal_res.is_anomaly

    # Evaluate defect image
    defect_img, defect_mask = _generate_synthetic_component_image("metal_nut", defect_type="bent", seed=42)
    defect_res = detector.predict(defect_img)
    assert defect_res.anomaly_score >= detector.threshold_pass
    assert defect_res.is_anomaly

    # Test heatmap overlay generation
    overlay = PatchCoreAnomalyDetector.generate_heatmap_overlay(defect_img, defect_res.heatmap)
    assert overlay.shape == defect_img.shape
    assert overlay.dtype == np.uint8


def test_defect_classifier_inference_and_calibration() -> None:
    """Verify 7-class defect classifier predictions and temperature scaling."""
    classifier = DefectClassifier(classes=DEFAULT_DEFECT_CLASSES, temperature=1.34)

    # Test with each defect category
    for label in DEFAULT_DEFECT_CLASSES:
        img, _ = _generate_synthetic_component_image("steel_sheet", defect_type=label if label != "good" else None, seed=12)
        res = classifier.predict(img)

        assert res.predicted_class in DEFAULT_DEFECT_CLASSES
        assert 0.0 <= res.confidence <= 1.0
        assert len(res.calibrated_probabilities) == 7
        assert abs(sum(res.calibrated_probabilities.values()) - 1.0) < 1e-4
        assert res.inference_ms < 50.0


def test_mlops_manifest_and_registry(tmp_path) -> None:
    """Verify MLOps dataset manifest hashing and model registry stage promotion."""
    # Test dHash perceptual hashing
    img1 = np.zeros((100, 100, 3), dtype=np.uint8)
    img2 = np.copy(img1)
    img3 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

    h1 = compute_dhash(img1)
    h2 = compute_dhash(img2)
    h3 = compute_dhash(img3)

    assert h1 == h2
    assert isinstance(h1, int)
    assert isinstance(h3, int)

    # Test registry
    reg_path = tmp_path / "model_registry"
    registry = ModelRegistry(registry_root=reg_path)

    art = registry.register_model(
        model_name="patchcore_metal_nut",
        version="v1.0.0",
        artifact_path="models/metal_nut_v1.npz",
        stage=ModelStage.CANDIDATE,
        metrics={"image_auroc": 0.985, "pixel_auroc": 0.942},
    )
    assert art.stage == ModelStage.CANDIDATE

    promoted = registry.promote_candidate("patchcore_metal_nut", "v1.0.0", promoted_by="mehmet")
    assert promoted is True

    prod_model = registry.get_production_model("patchcore_metal_nut")
    assert prod_model is not None
    assert prod_model.version == "v1.0.0"


def test_full_m1_m2_evaluation_gates() -> None:
    """Full integration check of M1 and M2 evaluation benchmarks against production targets."""
    # M1 Anomaly baselines
    m1_report = evaluate_anomaly_baselines()
    assert m1_report.all_categories_passed
    assert m1_report.mean_image_auroc >= 0.95
    assert m1_report.mean_pixel_auroc >= 0.92
    assert m1_report.mean_pro_score >= 0.85
    assert m1_report.overall_p95_latency_ms < 100.0

    # M2 Defect classifier
    m2_report = evaluate_defect_classifier()
    assert m2_report.passed_gate
    assert m2_report.macro_f1 >= 0.95
    assert m2_report.expected_calibration_error < 0.05
    assert m2_report.p95_latency_ms < 50.0
