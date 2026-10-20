"""Hierarchical contract clause segmenter with span grounding and bounding box mapping."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from fieldkit_common.logging import get_logger

from fieldkit_docai.contracts.models import ContractClause
from fieldkit_docai.models import LayoutBlock, PageResult

logger = get_logger("fieldkit.docai.contracts.segmenter")

# Regex to match numbered sections, articles, or German § paragraphs
# Groups:
# 1: Full numbering identifier (e.g. "1.1", "§ 2", "ARTICLE III", "Clause 4")
# 2: Optional title on same line
SECTION_PATTERNS = [
    # German § paragraphs: e.g. "§ 1 Vertragsgegenstand" or "§ 2.1 Haftung"
    re.compile(
        r"(?:^|\n)(?P<prefix>§\s*(?P<sec_num>\d+(?:\.\d+)*))\s*(?P<title>[^\n]+)?",
        re.MULTILINE,
    ),
    # Articles / Clauses: e.g. "ARTICLE II - PAYMENT" or "Clause 3.1"
    re.compile(
        r"(?:^|\n)(?P<prefix>(?:ARTICLE|Article|Art\.|CLAUSE|Clause|SECTION|Section|Sec\.)\s+(?P<sec_num>[IVXLCDM\d]+(?:\.\d+)*))\s*[-:.]?\s*(?P<title>[^\n]+)?",
        re.MULTILINE,
    ),
    # Decimal numbering: e.g. "1. DEFINITIONS" or "2.1 In no event..."
    re.compile(
        r"(?:^|\n)(?P<prefix>(?P<sec_num>\d+(?:\.\d+)+|\d+\.))\s+(?P<title>[^\n]+)?",
        re.MULTILINE,
    ),
]


class HierarchicalClauseSegmenter:
    """Segments legal contracts into hierarchical, span-grounded clauses."""

    def __init__(self) -> None:
        pass

    def segment_text(self, text: str) -> list[ContractClause]:
        """Segment raw text into span-grounded clauses."""
        if not text.strip():
            return []

        # Find all candidate section boundaries
        boundaries: list[dict[str, Any]] = []

        for pat in SECTION_PATTERNS:
            for match in pat.finditer(text):
                # Calculate the start of the section prefix
                match_start = match.start()
                if text[match_start] == "\n":
                    match_start += 1

                prefix = match.group("prefix")
                sec_num = match.group("sec_num").rstrip(".")
                title = (match.group("title") or "").strip()

                boundaries.append({
                    "start": match_start,
                    "prefix": prefix,
                    "sec_num": sec_num,
                    "title": title,
                })

        # Deduplicate overlapping matches by start position
        boundaries.sort(key=lambda b: b["start"])
        filtered_boundaries: list[dict[str, Any]] = []
        for b in boundaries:
            if not filtered_boundaries:
                filtered_boundaries.append(b)
            else:
                last = filtered_boundaries[-1]
                # Avoid overlapping starts within short window
                if b["start"] > last["start"] + len(last["prefix"]):
                    filtered_boundaries.append(b)

        # If no structured section boundaries found, treat whole text as single clause
        if not filtered_boundaries:
            return [
                ContractClause(
                    clause_id="clause_0",
                    section_number="",
                    title="",
                    text=text,
                    page_idx=0,
                    char_start=0,
                    char_end=len(text),
                )
            ]

        # Extract clauses between consecutive boundaries
        clauses: list[ContractClause] = []
        for i, b in enumerate(filtered_boundaries):
            start = b["start"]
            end = filtered_boundaries[i + 1]["start"] if i + 1 < len(filtered_boundaries) else len(text)
            clause_text = text[start:end]

            # Invariant: text[start:end] == clause_text
            clean_sec_num = b["sec_num"]
            clause_id = f"sec_{clean_sec_num.replace('.', '_')}_{i}"

            clauses.append(
                ContractClause(
                    clause_id=clause_id,
                    section_number=clean_sec_num,
                    title=b["title"],
                    text=clause_text,
                    page_idx=0,
                    char_start=start,
                    char_end=end,
                )
            )

        # Resolve parent-child relationships
        self._link_hierarchy(clauses)
        return clauses

    def segment_pages(self, pages: Sequence[PageResult]) -> list[ContractClause]:
        """Segment multi-page document into clauses with bounding box grounding."""
        if not pages:
            return []

        # Concatenate text while recording page character start/end intervals
        full_text_parts: list[str] = []
        page_char_map: list[tuple[int, int, PageResult]] = []
        current_offset = 0

        for p in pages:
            p_text = p.text
            start = current_offset
            end = start + len(p_text)
            page_char_map.append((start, end, p))
            full_text_parts.append(p_text)
            current_offset = end + 1  # newline separated

        full_text = "\n".join(full_text_parts)
        clauses = self.segment_text(full_text)

        # Assign page indices and layout block bounding boxes
        for clause in clauses:
            # Find primary page for clause
            for p_start, p_end, page in page_char_map:
                if clause.char_start >= p_start and clause.char_start < p_end:
                    clause.page_idx = page.page_idx
                    # Map to layout blocks if present
                    clause.bbox = self._compute_clause_bbox(clause, p_start, page.layout_blocks)
                    break

        return clauses

    def _compute_clause_bbox(
        self, clause: ContractClause, page_start_offset: int, blocks: list[LayoutBlock]
    ) -> list[int]:
        """Compute tight bounding box encompassing matching layout blocks on the page."""
        if not blocks:
            return [0, 0, 0, 0]

        matching_boxes: list[list[int]] = []
        for b in blocks:
            # If block text is a substring of the clause, include its bbox
            if b.text and b.text in clause.text:
                matching_boxes.append(b.bbox)

        if not matching_boxes:
            # Fallback to first block bbox or default
            return blocks[0].bbox if blocks else [0, 0, 0, 0]

        min_x0 = min(box[0] for box in matching_boxes)
        min_y0 = min(box[1] for box in matching_boxes)
        max_x1 = max(box[2] for box in matching_boxes)
        max_y1 = max(box[3] for box in matching_boxes)
        return [min_x0, min_y0, max_x1, max_y1]

    def _link_hierarchy(self, clauses: list[ContractClause]) -> None:
        """Establish hierarchical parent_clause_id pointers."""
        # Index clauses by their section_number
        sec_map = {c.section_number: c.clause_id for c in clauses if c.section_number}

        for clause in clauses:
            sec = clause.section_number
            if not sec:
                continue

            # Check decimal parent (e.g. "2.1" -> "2", "2.1.1" -> "2.1")
            if "." in sec:
                parent_sec = sec.rsplit(".", 1)[0]
                if parent_sec in sec_map:
                    clause.parent_clause_id = sec_map[parent_sec]
                    continue

            # Check roman / article parent
            for candidate in clauses:
                if candidate.clause_id != clause.clause_id and candidate.section_number:
                    if sec.startswith(f"{candidate.section_number}."):
                        clause.parent_clause_id = candidate.clause_id
                        break
