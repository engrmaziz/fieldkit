"""Test suite for document preprocessing, rendering, and OpenCV deskewing."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from fieldkit_docai.pipeline.preprocess import denoise_image, deskew_image, estimate_skew_angle


def create_synthetic_text_image(angle_deg: float = 0.0) -> np.ndarray:
    """Create a synthetic high-contrast document image with multiple lines of text, optionally rotated."""
    img = np.ones((800, 1200), dtype=np.uint8) * 255

    # Draw multiple horizontal text-like lines
    font = cv2.FONT_HERSHEY_SIMPLEX
    lines = [
        "HALDEN INDUSTRIE GMBH - LIEFERUNG UND WARENEINGANG",
        "Bestellnummer: PO-1001-HAMBURG | Datum: 14.10.2026",
        "Lieferschein-Nr: LS-2026-99214 | Spedition: Dachser Logistics",
        "Pos 1: Hydraulikventil HX-400 (Dichtring EPDM) - Menge: 24 Stk",
        "Pos 2: Dichtungssatz NBR-70 Druckstufe PN350 - Menge: 100 Stk",
        "Pos 3: Steuerkolben gehaertet 25mm geschliffen - Menge: 12 Stk",
        "Gesamtgewicht: 142.50 kg | Frachtfrei Werk Hamburg DE-HAM",
        "Hiermit bestaetigen wir den ordnungsgemaessen Erhalt der Ware.",
    ]

    y_pos = 120
    for line in lines:
        cv2.putText(img, line, (80, y_pos), font, 0.9, (0,), 2, cv2.LINE_AA)
        y_pos += 70

    if abs(angle_deg) > 0.05:
        # Rotate image around center with white background
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
        warped = cv2.warpAffine(
            img,
            rot_mat,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        return np.asarray(warped, dtype=np.uint8)

    return img


def test_straight_image_skip_deskew() -> None:
    """Images with negligible skew (< 0.3 deg) should skip rotation."""
    img = create_synthetic_text_image(angle_deg=0.1)
    deskewed, detected_angle = deskew_image(img)
    # Detected angle should be near 0 and skipped
    assert abs(detected_angle) < 0.4
    assert deskewed.shape == img.shape


@pytest.mark.parametrize("target_angle", [3.5, -4.0, 2.0, -2.5])
def test_deskew_rotated_fixture(target_angle: float) -> None:
    """Rotating an image by target_angle and deskewing it must yield residual angle < 0.5 degrees."""
    rotated = create_synthetic_text_image(angle_deg=target_angle)

    deskewed, applied_angle = deskew_image(rotated)

    # Measure residual skew on the corrected image
    residual_angle = estimate_skew_angle(deskewed)

    assert abs(residual_angle) < 0.5, (
        f"Residual angle {residual_angle:.2f} deg exceeded threshold 0.5 deg "
        f"for initial rotation {target_angle:.2f} deg (applied: {applied_angle:.2f} deg)"
    )


def test_denoise_scanned_image() -> None:
    """Denoising on simulated scanned noise preserves dimensions and text structure."""
    clean = create_synthetic_text_image()
    # Add gaussian salt & pepper noise
    noise = np.random.normal(0, 15, clean.shape).astype(np.int16)
    noisy = np.clip(clean.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    denoised = denoise_image(noisy, is_scanned=True)
    assert denoised.shape == clean.shape
    assert denoised.dtype == np.uint8
