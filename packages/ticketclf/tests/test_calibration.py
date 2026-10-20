"""Unit tests for post-hoc temperature scaling probability calibration."""

from pathlib import Path

import numpy as np
from fieldkit_ticketclf.calibration import TemperatureScaler, nll_loss, softmax


def test_softmax_properties() -> None:
    """Verifies that softmax sums to 1.0 and handles large values stably."""
    logits = np.array([[1000.0, 1001.0, 1002.0], [-1000.0, 0.0, 1000.0]])
    probs = softmax(logits)

    assert probs.shape == (2, 3)
    assert np.allclose(probs.sum(axis=-1), [1.0, 1.0])
    assert not np.any(np.isnan(probs))


def test_nll_loss_calculation() -> None:
    """Verifies that nll_loss computes negative log likelihood accurately."""
    logits = np.array([[2.0, 0.5, 0.1], [0.1, 3.0, 0.2]])
    labels = np.array([0, 1])

    loss_1 = nll_loss(1.0, logits, labels)
    loss_high = nll_loss(10.0, logits, labels)

    assert loss_1 > 0
    assert loss_high > 0
    # Overly high temperature blunts correct predictions, increasing loss
    assert loss_high > loss_1


def test_temperature_scaler_fit_and_calibrate(tmp_path: Path) -> None:
    """Verifies optimization of T and serialization / deserialization."""
    rng = np.random.RandomState(42)
    n_samples = 200

    # Overconfident uncalibrated logits
    logits_q = rng.randn(n_samples, 6) * 4.0
    labels_q = np.argmax(logits_q + rng.randn(n_samples, 6) * 1.5, axis=-1)

    logits_p = rng.randn(n_samples, 4) * 3.5
    labels_p = np.argmax(logits_p + rng.randn(n_samples, 4) * 1.2, axis=-1)

    scaler = TemperatureScaler()
    scaler.fit(logits_q, labels_q, logits_p, labels_p)

    assert scaler.is_fitted
    assert scaler.temperature_queue > 0.05
    assert scaler.temperature_priority > 0.05

    # Verify probability calibration output shape and sum
    q_probs = scaler.calibrate_queue(logits_q[:5])
    p_probs = scaler.calibrate_priority(logits_p[:5])

    assert q_probs.shape == (5, 6)
    assert p_probs.shape == (5, 4)
    assert np.allclose(q_probs.sum(axis=-1), 1.0)
    assert np.allclose(p_probs.sum(axis=-1), 1.0)

    # Save and reload
    save_file = tmp_path / "temperature_scaler.json"
    scaler.save(save_file)
    assert save_file.exists()

    loaded = TemperatureScaler.load(save_file)
    assert loaded.is_fitted
    assert loaded.temperature_queue == scaler.temperature_queue
    assert loaded.temperature_priority == scaler.temperature_priority
