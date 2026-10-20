from pathlib import Path

import numpy as np
import pytest
from fieldkit_ticketclf.calibration import TemperatureScaler
from fieldkit_ticketclf.infer import ONNXTicketClassifier, TicketPrediction


def test_ticket_prediction_schema() -> None:
    """Verifies schema validation and probability structures."""
    pred = TicketPrediction(
        queue="technical_defect",
        priority="high",
        confidence=0.9421,
        queue_probabilities={"technical_defect": 0.9421, "order_delivery": 0.0579},
        priority_probabilities={"high": 0.88, "medium": 0.12},
        latency_ms=12.4,
    )
    assert pred.queue == "technical_defect"
    assert pred.priority == "high"
    assert 0.0 <= pred.confidence <= 1.0
    assert pred.latency_ms > 0


def test_missing_model_raises_actionable_error(tmp_path: Path) -> None:
    """Verifies that attempting to load a non-existent model raises a helpful error."""
    non_existent = tmp_path / "model_int8.onnx"
    with pytest.raises(FileNotFoundError, match="Kaggle"):
        ONNXTicketClassifier(model_path=non_existent, allow_mock=False)


def test_mock_onnx_classifier_prediction() -> None:
    """Verifies end-to-end prediction pipeline in mock mode."""
    classifier = ONNXTicketClassifier(allow_mock=True)
    assert classifier.is_loaded

    texts = [
        "Oil leak spraying from hydraulic directional valve on line 3 at DE-HAM",
        "Missing packing slip and invoice for order PO-45892",
    ]
    results = classifier.predict(texts)

    assert len(results) == 2
    for res in results:
        assert isinstance(res, TicketPrediction)
        assert res.queue in [
            "technical_defect",
            "order_delivery",
            "returns_rma",
            "billing_inquiry",
            "general_inquiry",
            "other",
        ]
        assert res.priority in ["low", "medium", "high", "critical"]
        assert 0.0 <= res.confidence <= 1.0
        assert res.latency_ms >= 0.0
        assert len(res.queue_probabilities) == 6
        assert len(res.priority_probabilities) == 4


def test_temperature_calibration_applied_during_inference() -> None:
    """Verifies that TemperatureScaler modifies prediction probabilities."""
    scaler = TemperatureScaler(temperature_queue=2.5, temperature_priority=2.0)
    scaler.is_fitted = True

    classifier = ONNXTicketClassifier(scaler=scaler, allow_mock=True)
    results = classifier.predict(["Severe vibration in hydraulic pump HX-200"])
    assert len(results) == 1

    # Probability sum should be 1.0
    q_probs = list(results[0].queue_probabilities.values())
    assert np.isclose(sum(q_probs), 1.0, atol=1e-4)
