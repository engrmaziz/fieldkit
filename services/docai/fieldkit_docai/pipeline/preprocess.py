"""Document preprocessing, page rendering at 200 DPI, OpenCV deskewing and denoising."""

from __future__ import annotations

import io

import cv2
import numpy as np
import pymupdf
from PIL import Image


def render_pdf_pages_to_images(
    content: bytes,
    dpi: int = 200,
) -> list[tuple[np.ndarray, pymupdf.Page | None]]:
    """Render PDF pages at 200 DPI into numpy image arrays (BGR) with associated PyMuPDF page objects.

    Uses PyMuPDF (fitz) native pixmap rendering for ultra-fast, dependency-free rendering on any OS.
    """
    doc = pymupdf.open(stream=content, filetype="pdf")
    pages: list[tuple[np.ndarray, pymupdf.Page | None]] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # Calculate matrix for target DPI (72 DPI base)
        scale = dpi / 72.0
        mat = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Convert pixmap to numpy BGR image for OpenCV
        img_data = np.frombuffer(pix.samples, dtype=np.uint8)
        img = img_data.reshape((pix.height, pix.width, pix.n))
        if pix.n == 3:
            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pix.n == 1:
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            bgr = img

        pages.append((bgr, page))

    return pages


def render_image_bytes(content: bytes) -> tuple[np.ndarray, None]:
    """Load standard image bytes (PNG, JPEG, TIFF) into BGR numpy array."""
    pil_img: Image.Image = Image.open(io.BytesIO(content)).convert("RGB")
    rgb = np.array(pil_img)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return bgr, None


def estimate_skew_angle(image: np.ndarray) -> float:
    """Estimate document skew angle using minAreaRect on text mask.

    Returns:
        float: Estimated skew angle in degrees.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # Otsu thresholding with inversion (text pixels become white foreground)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    # Find text coordinates
    pts = cv2.findNonZero(thresh)
    if pts is None or len(pts) < 50:
        return 0.0

    rect = cv2.minAreaRect(pts)
    box_w, box_h = rect[1]
    box_angle = rect[2]

    # OpenCV 4.5+ angle normalization
    if box_w < box_h:
        skew = 90.0 + box_angle
    else:
        skew = box_angle

    # Bound skew within [-45, 45] degrees
    if skew > 45.0:
        skew -= 90.0
    elif skew < -45.0:
        skew += 90.0

    return float(skew)


def deskew_image(image: np.ndarray, min_angle_threshold: float = 0.3) -> tuple[np.ndarray, float]:
    """Deskew document image using OpenCV minAreaRect.

    Skips rotation if estimated skew is smaller than min_angle_threshold (default 0.3 deg).

    Returns:
        tuple[np.ndarray, float]: (deskewed_image, applied_angle_degrees)
    """
    skew = estimate_skew_angle(image)

    if abs(skew) < min_angle_threshold:
        return image, 0.0

    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    # In OpenCV, rotation is counter-clockwise for positive angle.
    rot_matrix = cv2.getRotationMatrix2D(center, skew, 1.0)

    # White background for rotated border
    border_val = (255, 255, 255) if len(image.shape) == 3 else 255
    deskewed = cv2.warpAffine(
        image,
        rot_matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_val,
    )

    return deskewed, skew


def denoise_image(image: np.ndarray, is_scanned: bool = False) -> np.ndarray:
    """Apply selective denoising using fastNlMeansDenoising on scanned documents."""
    if not is_scanned:
        return image

    if len(image.shape) == 3:
        # Color denoising
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    else:
        # Grayscale denoising
        return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
