"""Data models for contract clause segmentation, grounding, and CUAD classification."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CUADCategory(StrEnum):
    """Core CUAD (Contract Understanding Atticus Dataset) clause categories."""

    LIMITATION_OF_LIABILITY = "Limitation of Liability"
    CAP_ON_LIABILITY = "Cap on Liability"
    INDEMNIFICATION = "Indemnification"
    GOVERNING_LAW = "Governing Law"
    JURISDICTION = "Jurisdiction"
    TERMINATION_FOR_CONVENIENCE = "Termination for Convenience"
    NOTICE_PERIOD_TERMINATION = "Notice Period To Terminate"
    NON_COMPETE = "Non-Compete"
    EXCLUSIVITY = "Exclusivity"
    CONFIDENTIALITY = "Confidentiality"
    IP_ASSIGNMENT = "IP Assignment"
    WARRANTY = "Warranty"
    AUDIT_RIGHTS = "Audit Rights"
    FORCE_MAJEURE = "Force Majeure"
    INSURANCE = "Insurance"
    PRICE_PAYMENT_TERMS = "Price and Payment Terms"
    CHANGE_OF_CONTROL = "Change of Control"
    RENEWAL_TERM = "Renewal Term"
    OTHER = "Other"


class ContractClause(BaseModel):
    """Segmented, span-grounded contract clause entity."""

    clause_id: str = Field(description="Unique clause identifier e.g. 'sec_2_1'")
    section_number: str = Field(default="", description="Hierarchical numbering e.g. '2.1' or '§ 4'")
    title: str = Field(default="", description="Section or clause heading")
    text: str = Field(description="Full grounded text of the clause")
    page_idx: int = Field(default=0, ge=0, description="0-indexed page number")
    char_start: int = Field(ge=0, description="Starting character index in full document text")
    char_end: int = Field(ge=0, description="Ending character index in full document text")
    bbox: list[int] = Field(
        default_factory=lambda: [0, 0, 0, 0],
        description="[x0, y0, x1, y1] bounding box in page pixels",
    )
    parent_clause_id: str | None = Field(
        default=None,
        description="Parent clause id if hierarchical child (e.g. 'sec_2' for 'sec_2_1')",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Assigned CUAD clause category labels",
    )
    category_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Classification confidence scores per category",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra clause-level metadata or flags",
    )


class ContractDocument(BaseModel):
    """Structured representation of a parsed contract."""

    contract_id: str
    title: str = ""
    parties: list[str] = Field(default_factory=list)
    governing_law: str | None = None
    clauses: list[ContractClause] = Field(default_factory=list)
    full_text: str = ""
    page_count: int = 1
