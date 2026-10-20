"""OCR and text layer extraction with PyMuPDF native layer check and Tesseract fallback."""

from __future__ import annotations

import cv2
import numpy as np
import pymupdf
import pytesseract
from fieldkit_common.logging import get_logger
from fieldkit_docai.models import WordBox
from pytesseract import Output

logger = get_logger("fieldkit.docai.ocr")


def extract_page_text_and_boxes(
    page_image: np.ndarray,
    pdf_page: pymupdf.Page | None = None,
    dpi: int = 200,
) -> tuple[str, list[WordBox], str]:
    """Extract text and word-level bounding boxes from a document page.

    1. Checks if PyMuPDF native text layer has > 50 characters.
    2. If text layer is present, extracts words and maps coordinates to page_image pixels.
    3. If text layer is absent or sparse (scanned PDF or raw image), runs Tesseract deu+eng.

    Returns:
        tuple[str, list[WordBox], str]: (full_text, word_boxes, source)
    """
    h_img, w_img = page_image.shape[:2]

    # 1. Native text layer check
    if pdf_page is not None:
        raw_text = pdf_page.get_text()
        if len(raw_text.strip()) > 50:
            # Native text layer present
            scale = dpi / 72.0
            word_boxes: list[WordBox] = []

            # get_text("words") returns tuples: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
            for w in pdf_page.get_text("words"):
                x0 = int(round(w[0] * scale))
                y0 = int(round(w[1] * scale))
                x1 = int(round(w[2] * scale))
                y1 = int(round(w[3] * scale))
                word_text = str(w[4]).strip()
                if word_text:
                    word_boxes.append(
                        WordBox(
                            text=word_text,
                            bbox=[max(0, x0), max(0, y0), min(w_img, x1), min(h_img, y1)],
                            confidence=1.0,
                        )
                    )
            return raw_text, word_boxes, "native"

    # 2. Tesseract OCR Fallback
    try:
        # Fast path: check if page has any foreground text pixels
        gray = (
            cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
            if len(page_image.shape) == 3
            else page_image
        )
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        pts = cv2.findNonZero(thresh)
        if pts is None or len(pts) < 15:
            return "", [], "tesseract_empty"

        # pytesseract image_to_data with PSM 11 for high speed
        data = pytesseract.image_to_data(
            page_image,
            lang="deu+eng",
            config="--psm 11",
            output_type=Output.DICT,
        )
        words: list[str] = []
        word_boxes = []

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            word_str = data["text"][i].strip()
            conf_val = float(data["conf"][i])
            if word_str and conf_val >= 0:
                words.append(word_str)
                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])
                word_boxes.append(
                    WordBox(
                        text=word_str,
                        bbox=[x, y, x + w, y + h],
                        confidence=round(max(0.0, min(1.0, conf_val / 100.0)), 3),
                    )
                )

        full_text = " ".join(words)
        return full_text, word_boxes, "tesseract"

    except Exception as exc:
        logger.warning("tesseract_ocr_unavailable_using_contour_fallback", error=str(exc))
        # Fallback heuristic using OpenCV contour detection
        gray = (
            cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
            if len(page_image.shape) == 3
            else page_image
        )
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        fallback_boxes: list[WordBox] = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 10 and h > 8:
                fallback_boxes.append(
                    WordBox(
                        text="[TEXT]",
                        bbox=[x, y, x + w, y + h],
                        confidence=0.85,
                    )
                )

        return "", fallback_boxes, "contour_fallback"
