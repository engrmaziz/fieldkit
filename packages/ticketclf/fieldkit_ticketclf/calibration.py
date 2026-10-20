"""Temperature scaling calibration for post-hoc classifier probability calibration.

Temperature scaling learns a single scalar parameter T > 0 per classification head
such that p_calibrated = softmax(z / T). It preserves the argmax predictions
while ensuring that confidence scores accurately reflect true empirical accuracy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
from scipy.optimize import minimize_scalar


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    x_max = np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x - x_max)
    return cast(np.ndarray, exp_x / np.sum(exp_x, axis=axis, keepdims=True))


def nll_loss(t: float, logits: np.ndarray, labels: np.ndarray) -> float:
    """Negative log-likelihood loss for temperature scalar T."""
    scaled_logits = logits / max(t, 1e-4)
    probs = softmax(scaled_logits, axis=-1)
    # Clip probabilities to avoid log(0)
    eps = 1e-12
    n = len(labels)
    log_probs = np.log(np.clip(probs[np.arange(n), labels], eps, 1.0))
    return -float(np.mean(log_probs))


class TemperatureScaler:
    """Post-hoc probability calibrator via temperature scaling."""

    def __init__(
        self,
        temperature_queue: float = 1.0,
        temperature_priority: float = 1.0,
    ) -> None:
        self.temperature_queue = max(temperature_queue, 1e-4)
        self.temperature_priority = max(temperature_priority, 1e-4)
        self.is_fitted: bool = False

    def fit(
        self,
        logits_queue: np.ndarray,
        labels_queue: np.ndarray,
        logits_priority: np.ndarray,
        labels_priority: np.ndarray,
    ) -> TemperatureScaler:
        """Find optimal temperature scalars on validation logits."""
        # Optimize temperature for queue logits
        res_q = minimize_scalar(
            nll_loss,
            args=(logits_queue, labels_queue),
            bounds=(0.05, 10.0),
            method="bounded",
        )
        self.temperature_queue = round(float(res_q.x), 4)

        # Optimize temperature for priority logits
        res_p = minimize_scalar(
            nll_loss,
            args=(logits_priority, labels_priority),
            bounds=(0.05, 10.0),
            method="bounded",
        )
        self.temperature_priority = round(float(res_p.x), 4)

        self.is_fitted = True
        return self

    def calibrate_queue(self, logits: np.ndarray) -> np.ndarray:
        """Return calibrated probabilities for queue logits."""
        return softmax(logits / self.temperature_queue, axis=-1)

    def calibrate_priority(self, logits: np.ndarray) -> np.ndarray:
        """Return calibrated probabilities for priority logits."""
        return softmax(logits / self.temperature_priority, axis=-1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature_queue": self.temperature_queue,
            "temperature_priority": self.temperature_priority,
            "is_fitted": self.is_fitted,
        }

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> TemperatureScaler:
        p = Path(path)
        if not p.exists():
            return cls(1.0, 1.0)
        data = json.loads(p.read_text(encoding="utf-8"))
        scaler = cls(
            temperature_queue=float(data.get("temperature_queue", 1.0)),
            temperature_priority=float(data.get("temperature_priority", 1.0)),
        )
        scaler.is_fitted = bool(data.get("is_fitted", False))
        return scaler
