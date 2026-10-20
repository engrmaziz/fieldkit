"""Layout and table analysis module for document page segmentation."""

from __future__ import annotations

import uuid

import cv2
import numpy as np
from fieldkit_docai.models import LayoutBlock, WordBox


def segment_page_layout(
    page_image: np.ndarray,
    word_boxes: list[WordBox],
    page_idx: int = 0,
) -> list[LayoutBlock]:
    """Segment page image and word boxes into structural layout blocks (header, table, key_value, paragraph, footer)."""
    h_img, w_img = page_image.shape[:2]
    blocks: list[LayoutBlock] = []

    if not word_boxes:
        return blocks

    # 1. Detect tabular grid lines using morphological horizontal and vertical kernels
    gray = (
        cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY) if len(page_image.shape) == 3 else page_image
    )
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    # Horizontal and vertical lines
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w_img * 0.05), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(h_img * 0.03)))

    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)
    table_mask = cv2.add(h_lines, v_lines)

    table_contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    table_boxes: list[list[int]] = []
    for c in table_contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > w_img * 0.4 and h > h_img * 0.08:
            table_boxes.append([x, y, x + w, y + h])

    # 2. Assign word boxes to vertical regions
    header_words: list[WordBox] = []
    footer_words: list[WordBox] = []
    table_words: list[WordBox] = []
    body_words: list[WordBox] = []

    for wb in word_boxes:
        bx0, by0, bx1, by1 = wb.bbox
        cy = (by0 + by1) / 2.0

        in_table = False
        for tb in table_boxes:
            if tb[0] <= bx0 and bx1 <= tb[2] and tb[1] <= cy <= tb[3]:
                table_words.append(wb)
                in_table = True
                break
        if in_table:
            continue

        if cy < h_img * 0.18:
            header_words.append(wb)
        elif cy > h_img * 0.88:
            footer_words.append(wb)
        else:
            body_words.append(wb)

    # Helper to create block
    def make_block(words: list[WordBox], b_type: str) -> LayoutBlock | None:
        if not words:
            return None
        min_x = min(w.bbox[0] for w in words)
        min_y = min(w.bbox[1] for w in words)
        max_x = max(w.bbox[2] for w in words)
        max_y = max(w.bbox[3] for w in words)
        text = " ".join(w.text for w in words)
        return LayoutBlock(
            block_id=f"blk-{page_idx}-{uuid.uuid4().hex[:6]}",
            page_idx=page_idx,
            block_type=b_type,
            bbox=[min_x, min_y, max_x, max_y],
            text=text,
            confidence=round(float(np.mean([w.confidence for w in words])), 3),
        )

    # Create Header block
    b_hdr = make_block(header_words, "header")
    if b_hdr:
        blocks.append(b_hdr)

    # Create Table blocks
    if table_boxes:
        for idx, tb in enumerate(table_boxes):
            t_words = [
                w
                for w in table_words
                if tb[0] <= w.bbox[0] and w.bbox[2] <= tb[2] and tb[1] <= w.bbox[1] <= tb[3]
            ]
            text = " ".join(w.text for w in t_words)
            blocks.append(
                LayoutBlock(
                    block_id=f"blk-{page_idx}-tbl-{idx}",
                    page_idx=page_idx,
                    block_type="table",
                    bbox=tb,
                    text=text,
                    confidence=0.95,
                )
            )
    elif table_words:
        b_tbl = make_block(table_words, "table")
        if b_tbl:
            blocks.append(b_tbl)

    # Create Key-Value and Paragraph blocks from body words
    if body_words:
        # Group body words by vertical lines
        sorted_body = sorted(body_words, key=lambda w: (w.bbox[1] // 30, w.bbox[0]))
        kv_words = [
            w
            for w in sorted_body
            if any(k in w.text.lower() for k in [":", "nr", "no", "datum", "date", "po-", "pos"])
        ]
        para_words = [w for w in sorted_body if w not in kv_words]

        b_kv = make_block(kv_words, "key_value")
        if b_kv:
            blocks.append(b_kv)

        b_para = make_block(para_words, "paragraph")
        if b_para:
            blocks.append(b_para)

    # Create Footer block
    b_ftr = make_block(footer_words, "footer")
    if b_ftr:
        blocks.append(b_ftr)

    return blocks
