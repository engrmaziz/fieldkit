"""Image preprocessing, ROI extraction, and keypoint-based reference alignment."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessResult:
    """Preprocessed inspection sample ready for model inference."""

    image: np.ndarray  # (H, W, 3) uint8 or float32
    aligned: bool
    inlier_count: int
    is_misaligned: bool
    transform_matrix: np.ndarray | None = None


class InspectionPreprocessor:
    """Handles ROI cropping, bicubic resizing, normalization, and ORB reference alignment."""

    def __init__(
        self,
        target_size: tuple[int, int] = (256, 256),
        roi: list[int] | None = None,
        min_inliers: int = 15,
        alignment_enabled: bool = True,
    ) -> None:
        self.target_size = target_size
        self.roi = roi  # [x1, y1, x2, y2]
        self.min_inliers = min_inliers
        self.alignment_enabled = alignment_enabled

        self._reference_image: np.ndarray | None = None
        self._ref_keypoints: list[cv2.KeyPoint] | None = None
        self._ref_descriptors: np.ndarray | None = None

        self._orb = cv2.ORB_create(nfeatures=500)  # type: ignore[attr-defined]
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def set_reference_image(self, ref_image: np.ndarray) -> None:
        """Register the gold-standard component reference image for spatial alignment."""
        if ref_image is None or ref_image.size == 0:
            return

        # Apply ROI crop if configured
        if self.roi and len(self.roi) == 4:
            x1, y1, x2, y2 = self.roi
            ref_image = ref_image[y1:y2, x1:x2]

        # Resize to target size
        ref_image = cv2.resize(ref_image, self.target_size, interpolation=cv2.INTER_AREA)
        self._reference_image = ref_image

        gray = cv2.cvtColor(ref_image, cv2.COLOR_BGR2GRAY) if len(ref_image.shape) == 3 else ref_image
        self._ref_keypoints, self._ref_descriptors = self._orb.detectAndCompute(gray, None)

    def align(self, image: np.ndarray) -> tuple[np.ndarray, bool, int, np.ndarray | None]:
        """Align test component image to the reference image via ORB feature homography."""
        if not self.alignment_enabled or self._ref_descriptors is None or self._ref_keypoints is None:
            return image, True, 0, None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        kps, descs = self._orb.detectAndCompute(gray, None)

        if descs is None or len(descs) < 8 or len(self._ref_descriptors) < 8:
            # Insufficient keypoints to compute transformation
            return image, False, 0, None

        matches = self._matcher.match(descs, self._ref_descriptors)
        if len(matches) < 8:
            return image, False, len(matches), None

        # Sort matches by distance
        matches = sorted(matches, key=lambda m: m.distance)
        good_matches = matches[:50]

        src_pts = np.float32([kps[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([self._ref_keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Estimate partial affine/homography transform with RANSAC
        homog_matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        inlier_count = int(np.sum(mask)) if mask is not None else 0
        if homog_matrix is None or inlier_count < self.min_inliers:
            return image, False, inlier_count, None

        # Warp image into reference perspective
        h, w = self.target_size
        aligned = cv2.warpPerspective(image, homog_matrix, (w, h), flags=cv2.INTER_LINEAR)
        return aligned, True, inlier_count, homog_matrix

    def preprocess(self, image: np.ndarray) -> PreprocessResult:
        """Full preprocessing pipeline: ROI crop -> resize -> reference alignment."""
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or invalid")

        img = image.copy()

        # 1. ROI Crop
        if self.roi and len(self.roi) == 4:
            x1, y1, x2, y2 = self.roi
            h, w = img.shape[:2]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))
            img = img[y1:y2, x1:x2]

        # 2. Resize to target dimension
        img = cv2.resize(img, self.target_size, interpolation=cv2.INTER_AREA)

        # 3. Reference alignment
        aligned_img, is_aligned, inliers, transform_mat = self.align(img)
        is_misaligned = self.alignment_enabled and not is_aligned

        return PreprocessResult(
            image=aligned_img,
            aligned=is_aligned,
            inlier_count=inliers,
            is_misaligned=is_misaligned,
            transform_matrix=transform_mat,
        )
