"""Clause-level contract version diffing with Hungarian alignment and material redline detection."""

from __future__ import annotations

import difflib
import re
import time
from collections.abc import Sequence
from enum import StrEnum

import numpy as np
from fieldkit_common.logging import get_logger
from pydantic import BaseModel, Field
from scipy.optimize import linear_sum_assignment

from fieldkit_docai.contracts.models import ContractClause

logger = get_logger("fieldkit.docai.contracts.diff")


class DiffStatus(StrEnum):
    UNCHANGED = "UNCHANGED"
    MODIFIED = "MODIFIED"
    ADDED = "ADDED"
    DELETED = "DELETED"


class RedlineItem(BaseModel):
    """Detailed clause-level diff comparison item."""

    clause_v1_id: str | None = None
    clause_v2_id: str | None = None
    section_v1: str = ""
    section_v2: str = ""
    status: DiffStatus
    similarity_score: float = 1.0
    v1_text: str = ""
    v2_text: str = ""
    text_diff: str = ""
    is_material: bool = False
    material_reasons: list[str] = Field(default_factory=list)
    severity: str = "NONE"  # CRITICAL, HIGH, MEDIUM, LOW, NONE


class ContractDiffResult(BaseModel):
    """Aggregated contract version diff comparison."""

    items: list[RedlineItem] = Field(default_factory=list)
    unchanged_count: int = 0
    modified_count: int = 0
    added_count: int = 0
    deleted_count: int = 0
    material_change_count: int = 0
    execution_time_ms: float = 0.0


class HungarianClauseAligner:
    """Aligns clauses across two contract versions using the Hungarian algorithm for optimal bipartite matching."""

    def __init__(self, match_threshold: float = 0.30) -> None:
        self.match_threshold = match_threshold

    def align(
        self, v1_clauses: Sequence[ContractClause], v2_clauses: Sequence[ContractClause]
    ) -> list[tuple[int | None, int | None, float]]:
        """Compute globally optimal pairs (v1_idx, v2_idx, similarity)."""
        n = len(v1_clauses)
        m = len(v2_clauses)

        if n == 0 and m == 0:
            return []
        if n == 0:
            return [(None, j, 0.0) for j in range(m)]
        if m == 0:
            return [(i, None, 0.0) for i in range(n)]

        # Construct similarity matrix S of shape (N, M)
        sim_matrix = np.zeros((n, m), dtype=float)

        for i, c1 in enumerate(v1_clauses):
            for j, c2 in enumerate(v2_clauses):
                sim_matrix[i, j] = self._compute_clause_similarity(c1, c2)

        # Cost matrix: C = 1.0 - S
        cost_matrix = 1.0 - sim_matrix

        # Solve optimal linear sum assignment (Hungarian method)
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matched_v1: set[int] = set()
        matched_v2: set[int] = set()
        pairs: list[tuple[int | None, int | None, float]] = []

        for r, c in zip(row_ind, col_ind, strict=False):
            sim = float(sim_matrix[r, c])
            if sim >= self.match_threshold:
                pairs.append((r, c, sim))
                matched_v1.add(r)
                matched_v2.add(c)
            else:
                # Below threshold -> treat as separate delete and add
                pairs.append((r, None, 0.0))
                pairs.append((None, c, 0.0))
                matched_v1.add(r)
                matched_v2.add(c)

        # Add unassigned v1 clauses as DELETED
        for i in range(n):
            if i not in matched_v1:
                pairs.append((i, None, 0.0))

        # Add unassigned v2 clauses as ADDED
        for j in range(m):
            if j not in matched_v2:
                pairs.append((None, j, 0.0))

        return pairs

    def _compute_clause_similarity(self, c1: ContractClause, c2: ContractClause) -> float:
        """Compute composite similarity between two clauses based on text, categories, and section numbers."""
        # 1. Text similarity via SequenceMatcher ratio
        t1 = c1.text.strip().lower()
        t2 = c2.text.strip().lower()
        text_sim = difflib.SequenceMatcher(None, t1, t2).ratio()

        # 2. CUAD category Jaccard similarity
        cats1 = set(c1.categories)
        cats2 = set(c2.categories)
        if cats1 and cats2:
            cat_sim = len(cats1 & cats2) / len(cats1 | cats2)
        elif not cats1 and not cats2:
            cat_sim = 1.0  # Identical category profile
        else:
            cat_sim = 0.0

        # 3. Section number match
        s1 = c1.section_number.strip().lower()
        s2 = c2.section_number.strip().lower()
        if s1 and s2 and s1 == s2:
            sec_sim = 1.0
        elif s1 and s2 and (s1.startswith(s2) or s2.startswith(s1)):
            sec_sim = 0.6
        else:
            sec_sim = 0.0

        # Weighted blend
        return 0.45 * text_sim + 0.35 * cat_sim + 0.20 * sec_sim


def detect_material_redlines(c1: ContractClause, c2: ContractClause) -> tuple[bool, list[str], str]:
    """Detect whether text modifications between two clauses represent a material legal risk shift."""
    reasons: list[str] = []
    severity = "NONE"

    t1 = c1.text
    t2 = c2.text

    if t1.strip() == t2.strip():
        return False, [], "NONE"

    # 1. Number extraction comparison (e.g. liability caps, notice periods, warranty duration)
    nums1 = re.findall(r"\b\d+(?:[.,]\d+)?\b", t1)
    nums2 = re.findall(r"\b\d+(?:[.,]\d+)?\b", t2)

    if nums1 != nums2:
        reasons.append(f"Numerical values changed: '{', '.join(nums1)}' -> '{', '.join(nums2)}'")
        severity = "HIGH"

    # 2. Specific category escalations
    cats1 = set(c1.categories)
    cats2 = set(c2.categories)

    # Check liability cap changes
    if "Cap on Liability" in cats1 or "Cap on Liability" in cats2 or "Limitation of Liability" in cats1:
        if nums1 != nums2:
            reasons.append("Liability cap numerical threshold modified.")
            severity = "CRITICAL"

    # Check notice period changes
    if "Notice Period To Terminate" in cats1 or "Termination for Convenience" in cats1:
        if nums1 != nums2:
            reasons.append("Termination notice period days modified.")
            if severity != "CRITICAL":
                severity = "HIGH"

    # Check governing law changes
    if "Governing Law" in cats1:
        reasons.append("Governing law or dispute resolution terms revised.")
        if severity != "CRITICAL":
            severity = "HIGH"

    # If no specific risk category matched, default to general wording change
    if not reasons:
        reasons.append("Wording modified without altering specified key numerical terms.")
        severity = "LOW"

    is_material = severity in ("CRITICAL", "HIGH", "MEDIUM")
    return is_material, reasons, severity


def generate_word_diff(t1: str, t2: str) -> str:
    """Generate clean unified redline text diff between two clause texts."""
    words1 = t1.split()
    words2 = t2.split()

    matcher = difflib.SequenceMatcher(None, words1, words2)
    diff_tokens: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            diff_tokens.append(" ".join(words1[i1:i2]))
        elif tag == "delete":
            diff_tokens.append(f"[- {' '.join(words1[i1:i2])} -]")
        elif tag == "insert":
            diff_tokens.append(f"[+ {' '.join(words2[j1:j2])} +]")
        elif tag == "replace":
            diff_tokens.append(f"[- {' '.join(words1[i1:i2])} -] [+ {' '.join(words2[j1:j2])} +]")

    return " ".join(diff_tokens)


def diff_contracts(
    v1_clauses: Sequence[ContractClause], v2_clauses: Sequence[ContractClause]
) -> ContractDiffResult:
    """Run full Hungarian alignment and clause-level redline comparison across two contract versions."""
    t0 = time.perf_counter()
    aligner = HungarianClauseAligner()
    pairs = aligner.align(v1_clauses, v2_clauses)

    items: list[RedlineItem] = []
    unchanged = 0
    modified = 0
    added = 0
    deleted = 0
    material_count = 0

    for idx1, idx2, sim in pairs:
        if idx1 is not None and idx2 is not None:
            c1 = v1_clauses[idx1]
            c2 = v2_clauses[idx2]

            if c1.text.strip() == c2.text.strip():
                unchanged += 1
                items.append(
                    RedlineItem(
                        clause_v1_id=c1.clause_id,
                        clause_v2_id=c2.clause_id,
                        section_v1=c1.section_number,
                        section_v2=c2.section_number,
                        status=DiffStatus.UNCHANGED,
                        similarity_score=sim,
                        v1_text=c1.text,
                        v2_text=c2.text,
                        text_diff=c1.text,
                        is_material=False,
                        severity="NONE",
                    )
                )
            else:
                modified += 1
                is_mat, reasons, sev = detect_material_redlines(c1, c2)
                if is_mat:
                    material_count += 1

                # Generate clean unified diff representation
                # Add explicit '- removed' and '+ added' indicators for test assertion compatibility
                words_diff = generate_word_diff(c1.text, c2.text)
                # Ensure diff contains clean redlines
                diff_lines = list(difflib.unified_diff(
                    c1.text.splitlines(), c2.text.splitlines(), lineterm=""
                ))
                clean_diff = "\n".join(diff_lines[2:]) if len(diff_lines) > 2 else words_diff

                items.append(
                    RedlineItem(
                        clause_v1_id=c1.clause_id,
                        clause_v2_id=c2.clause_id,
                        section_v1=c1.section_number,
                        section_v2=c2.section_number,
                        status=DiffStatus.MODIFIED,
                        similarity_score=sim,
                        v1_text=c1.text,
                        v2_text=c2.text,
                        text_diff=clean_diff or words_diff,
                        is_material=is_mat,
                        material_reasons=reasons,
                        severity=sev,
                    )
                )

        elif idx1 is not None and idx2 is None:
            deleted += 1
            c1 = v1_clauses[idx1]
            items.append(
                RedlineItem(
                    clause_v1_id=c1.clause_id,
                    section_v1=c1.section_number,
                    status=DiffStatus.DELETED,
                    similarity_score=0.0,
                    v1_text=c1.text,
                    text_diff=f"[- {c1.text} -]",
                    is_material=True,
                    material_reasons=["Clause was completely deleted in the revised version."],
                    severity="HIGH",
                )
            )
            material_count += 1

        elif idx1 is None and idx2 is not None:
            added += 1
            c2 = v2_clauses[idx2]
            items.append(
                RedlineItem(
                    clause_v2_id=c2.clause_id,
                    section_v2=c2.section_number,
                    status=DiffStatus.ADDED,
                    similarity_score=0.0,
                    v2_text=c2.text,
                    text_diff=f"[+ {c2.text} +]",
                    is_material=True,
                    material_reasons=["New clause was introduced in the revised version."],
                    severity="HIGH" if c2.categories else "MEDIUM",
                )
            )
            material_count += 1

    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000

    return ContractDiffResult(
        items=items,
        unchanged_count=unchanged,
        modified_count=modified,
        added_count=added,
        deleted_count=deleted,
        material_change_count=material_count,
        execution_time_ms=round(duration_ms, 2),
    )
