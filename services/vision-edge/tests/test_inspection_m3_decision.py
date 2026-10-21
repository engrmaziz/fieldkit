"""Tests for Project 6 M3: Decision Engine with Cost-Based Thresholds & 2% Audit Sampling."""

from __future__ import annotations

import numpy as np
from fieldkit_mlops.thresholds import (
    CostMatrixConfig,
    ThresholdOptimizationResult,
    evaluate_decision_cost,
    optimize_inspection_thresholds,
)
from fieldkit_vision.inspect.anomaly import AnomalyResult
from fieldkit_vision.inspect.classifier import DefectPrediction
from fieldkit_vision.inspect.decision import (
    DecisionAction,
    DecisionReason,
    InspectionDecisionEngine,
)
from fieldkit_vision.inspect.preprocess import PreprocessResult


def test_cost_matrix_evaluation() -> None:
    """Test cost calculation with asymmetric penalties."""
    cost_cfg = CostMatrixConfig(
        cost_false_pass=500.0,
        cost_false_reject=25.0,
        cost_review=5.0,
        max_review_budget=0.08,
    )

    # 100 items: 50 normal, 50 defective
    y_true = [0] * 50 + [1] * 50
    # Perfect decisions: 50 pass, 50 reject
    decisions_perfect = [DecisionAction.PASS] * 50 + [DecisionAction.REJECT] * 50
    perf_metrics = evaluate_decision_cost(y_true, decisions_perfect, cost_cfg)
    assert perf_metrics.total_cost == 0.0
    assert perf_metrics.escape_rate == 0.0
    assert perf_metrics.review_rate == 0.0

    # 2 escapes (defects marked PASS) and 4 human reviews
    decisions_flawed = (
        [DecisionAction.PASS] * 48
        + [DecisionAction.REVIEW] * 2  # 2 normal in review
        + [DecisionAction.PASS] * 2  # 2 escapes!
        + [DecisionAction.REVIEW] * 2  # 2 defects in review
        + [DecisionAction.REJECT] * 46
    )
    flawed_metrics = evaluate_decision_cost(y_true, decisions_flawed, cost_cfg)
    # Expected cost: 2 escapes * 500 = 1000, 4 reviews * 5 = 20 -> total 1020
    assert flawed_metrics.total_cost == 1020.0
    assert flawed_metrics.escapes == 2
    assert flawed_metrics.review_rate == 0.04  # 4/100 <= 8% budget


def test_threshold_optimizer_satisfies_review_budget() -> None:
    """Test threshold grid optimization minimizes cost while keeping review budget <= 8%."""
    rng = np.random.RandomState(42)
    # 200 normal samples (scores centered around 0.1)
    norm_scores = rng.normal(0.12, 0.06, 200).clip(0.0, 1.0)
    # 50 defect samples (scores centered around 0.7)
    defect_scores = rng.normal(0.72, 0.12, 50).clip(0.0, 1.0)
    # 10 borderline samples (scores between 0.35 and 0.50)
    border_scores = rng.uniform(0.35, 0.48, 10)

    y_true = [0] * 200 + [1] * 50 + [1] * 10
    scores = np.concatenate([norm_scores, defect_scores, border_scores])

    cost_cfg = CostMatrixConfig(
        cost_false_pass=500.0,
        cost_false_reject=25.0,
        cost_review=5.0,
        max_review_budget=0.08,
    )

    opt_result = optimize_inspection_thresholds(y_true, scores, cost_cfg)

    assert isinstance(opt_result, ThresholdOptimizationResult)
    assert 0.0 < opt_result.threshold_pass <= opt_result.threshold_reject < 1.0
    assert opt_result.metrics.review_rate <= 0.08  # Strict 8% budget constraint!
    assert opt_result.metrics.escape_rate == 0.0  # Zero escapes under high penalty!


def test_decision_engine_deterministic_routing() -> None:
    """Verify deterministic state machine routing across all operational scenarios."""
    cost_cfg = CostMatrixConfig()
    engine = InspectionDecisionEngine(
        threshold_pass=0.35,
        threshold_reject=0.65,
        threshold_classifier_conf=0.85,
        cost_matrix=cost_cfg,
    )

    dummy_prep_clean = PreprocessResult(
        image=np.zeros((256, 256, 3), dtype=np.uint8),
        aligned=True,
        inlier_count=45,
        is_misaligned=False,
    )
    dummy_heatmap = np.zeros((256, 256), dtype=np.float32)

    # 1. High confidence defect -> REJECT
    res_reject = engine.evaluate(
        prep_result=dummy_prep_clean,
        anomaly_result=AnomalyResult(
            anomaly_score=0.85,
            is_anomaly=True,
            heatmap=dummy_heatmap,
            max_pixel_score=0.9,
            inference_ms=5.0,
        ),
        defect_prediction=DefectPrediction(
            predicted_class="crazing",
            confidence=0.96,
            is_defect=True,
            calibrated_probabilities={"crazing": 0.96, "good": 0.01},
            inference_ms=3.0,
        ),
    )
    assert res_reject.action == DecisionAction.REJECT
    assert res_reject.reason == DecisionReason.CONFIRMED_DEFECT

    # 2. Borderline anomaly in grey-zone [0.35, 0.65] -> REVIEW
    res_borderline = engine.evaluate(
        prep_result=dummy_prep_clean,
        anomaly_result=AnomalyResult(
            anomaly_score=0.48,
            is_anomaly=True,
            heatmap=dummy_heatmap,
            max_pixel_score=0.55,
            inference_ms=5.0,
        ),
        defect_prediction=DefectPrediction(
            predicted_class="good",
            confidence=0.72,
            is_defect=False,
            calibrated_probabilities={"good": 0.72, "inclusion": 0.28},
            inference_ms=3.0,
        ),
    )
    assert res_borderline.action == DecisionAction.REVIEW
    assert res_borderline.reason == DecisionReason.BORDERLINE_ANOMALY

    # 3. Reference alignment failure -> REVIEW
    prep_misaligned = PreprocessResult(
        image=np.zeros((256, 256, 3), dtype=np.uint8),
        aligned=False,
        inlier_count=5,
        is_misaligned=True,
    )
    res_align_fail = engine.evaluate(
        prep_result=prep_misaligned,
        anomaly_result=AnomalyResult(
            anomaly_score=0.10,
            is_anomaly=False,
            heatmap=dummy_heatmap,
            max_pixel_score=0.1,
            inference_ms=5.0,
        ),
        defect_prediction=DefectPrediction(
            predicted_class="good",
            confidence=0.98,
            is_defect=False,
            calibrated_probabilities={"good": 0.98},
            inference_ms=3.0,
        ),
    )
    assert res_align_fail.action == DecisionAction.REVIEW
    assert res_align_fail.reason == DecisionReason.ALIGNMENT_FAULT

    # 4. Low confidence classifier -> REVIEW
    res_low_conf = engine.evaluate(
        prep_result=dummy_prep_clean,
        anomaly_result=AnomalyResult(
            anomaly_score=0.20,
            is_anomaly=False,
            heatmap=dummy_heatmap,
            max_pixel_score=0.2,
            inference_ms=5.0,
        ),
        defect_prediction=DefectPrediction(
            predicted_class="scratches",
            confidence=0.52,  # Low confidence < 0.85
            is_defect=True,
            calibrated_probabilities={"scratches": 0.52, "good": 0.48},
            inference_ms=3.0,
        ),
    )
    assert res_low_conf.action == DecisionAction.REVIEW
    assert res_low_conf.reason == DecisionReason.LOW_CONFIDENCE_CLASSIFICATION

    # 5. Clean component -> PASS
    res_clean = engine.evaluate(
        prep_result=dummy_prep_clean,
        anomaly_result=AnomalyResult(
            anomaly_score=0.08,
            is_anomaly=False,
            heatmap=dummy_heatmap,
            max_pixel_score=0.09,
            inference_ms=5.0,
        ),
        defect_prediction=DefectPrediction(
            predicted_class="good",
            confidence=0.97,
            is_defect=False,
            calibrated_probabilities={"good": 0.97},
            inference_ms=3.0,
        ),
        item_id="clean_part_001",
    )
    assert res_clean.action in (DecisionAction.PASS, DecisionAction.REVIEW)  # may be selected for 2% audit


def test_seeded_random_audit_rate() -> None:
    """Verify 2% random audit rate on clean PASS items is exactly deterministic and close to 2%."""
    cost_cfg = CostMatrixConfig()
    engine = InspectionDecisionEngine(
        threshold_pass=0.35,
        threshold_reject=0.65,
        audit_rate=0.02,
        cost_matrix=cost_cfg,
    )
    dummy_prep = PreprocessResult(
        image=np.zeros((256, 256, 3), dtype=np.uint8),
        aligned=True,
        inlier_count=50,
        is_misaligned=False,
    )
    dummy_anom = AnomalyResult(
        anomaly_score=0.05,
        is_anomaly=False,
        heatmap=np.zeros((256, 256), dtype=np.float32),
        max_pixel_score=0.05,
        inference_ms=5.0,
    )
    dummy_pred = DefectPrediction(
        predicted_class="good",
        confidence=0.98,
        is_defect=False,
        calibrated_probabilities={"good": 0.98},
        inference_ms=3.0,
    )

    # Evaluate 1,000 clean items
    audit_count = 0
    total = 1000
    for i in range(total):
        item_id = f"nut_batch_{i:04d}"
        dec = engine.evaluate(
            prep_result=dummy_prep,
            anomaly_result=dummy_anom,
            defect_prediction=dummy_pred,
            item_id=item_id,
        )
        if dec.is_audit_sample:
            audit_count += 1
            assert dec.reason == DecisionReason.RANDOM_AUDIT

    measured_rate = audit_count / total
    # Should be approximately 2% (e.g. between 1% and 3.5%)
    assert 0.010 <= measured_rate <= 0.035
