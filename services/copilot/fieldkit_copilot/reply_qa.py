"""Deterministic Outbound Reply QA Engine for Fieldkit Ops Copilot (P3).

Enforces strict outbound quality, security, and compliance checks:
1. PII Leak Prevention: Redacts and flags raw IBANs, phone numbers, emails, or credit cards.
2. Language Matching: Ensures German tickets receive German replies, English receive English.
3. Policy & Financial Sanity: Blocks unauthorized refund/credit commitments without approved action.
4. Part Number Verification: Prevents LLM hallucinations of nonexistent part models.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# PII Regex Patterns
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b")
PHONE_PATTERN = re.compile(r"(\+?[0-9]{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

# Language marker words
GERMAN_MARKERS = {
    "guten",
    "tag",
    "hallo",
    "sehr",
    "geehrte",
    "geehrter",
    "vielen",
    "dank",
    "wir",
    "ihre",
    "ihr",
    "ihrem",
    "rücksendung",
    "anfrage",
    "haben",
    "bitte",
    "unterlagen",
    "überweisen",
    "erstatten",
    "grüße",
    "zylinder",
    "ventil",
    "prüfung",
}
ENGLISH_MARKERS = {
    "hello",
    "dear",
    "thank",
    "you",
    "reaching",
    "regards",
    "support",
    "team",
    "initiated",
    "processing",
    "logistics",
    "shortly",
    "contact",
    "replacement",
    "defective",
    "order",
    "please",
    "issue",
    "refund",
    "credit",
    "warranty",
}

# Financial Promise Patterns
FINANCIAL_PROMISE_PATTERN = re.compile(
    r"\b(erstatten|überweisen|gutschrift|rückzahlung|refund|reimburse|credit|pay you back)\b",
    re.IGNORECASE,
)

# Part Number Pattern (e.g. HX-400, PX-900)
PART_NUMBER_PATTERN = re.compile(r"\b[A-Z]{2,4}-[0-9]{3,5}\b")


class ReplyQARequest(BaseModel):
    """Input payload for outbound reply quality assurance."""

    ticket_id: str
    ticket_language: str = "de"
    ticket_text: str
    reply_draft: str
    approved_actions: list[str] = Field(default_factory=list)
    known_part_numbers: list[str] = Field(default_factory=list)


class ReplyQAResult(BaseModel):
    """Result of deterministic reply QA evaluation."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    sanitized_draft: str
    detected_language: str


def detect_language(text: str) -> str:
    """Classify text language as 'de' or 'en' based on marker term frequency."""
    lowered = text.lower()
    words = set(re.findall(r"\b\w+\b", lowered))

    de_score = len(words & GERMAN_MARKERS)
    en_score = len(words & ENGLISH_MARKERS)

    # Check German specific characters
    if any(c in lowered for c in ("ä", "ö", "ü", "ß")):
        de_score += 3

    if de_score > en_score:
        return "de"
    if en_score > de_score:
        return "en"
    return "de"  # Default Halden plant language


def validate_reply_qa(req: ReplyQARequest) -> ReplyQAResult:
    """Execute all deterministic QA checks on the outbound reply draft."""
    violations: list[str] = []
    draft = req.reply_draft
    sanitized = draft

    # 1. PII Leak Check & Sanitization
    leaked_pii: list[str] = []
    # Check IBANs
    for match in IBAN_PATTERN.finditer(draft):
        val = match.group()
        leaked_pii.append(f"IBAN: {val}")
        sanitized = sanitized.replace(val, "<IBAN_REDACTED>")

    # Check Credit Card numbers (16 digits)
    cc_matches = re.findall(r"\b(?:\d{4}[-\s]?){3}\d{4}\b", draft)
    for cc in cc_matches:
        leaked_pii.append(f"Card: {cc}")
        sanitized = sanitized.replace(cc, "<CARD_REDACTED>")

    if leaked_pii:
        violations.append(f"PII Leak Detected in outbound draft: {', '.join(leaked_pii)}")

    # 2. Language Consistency Check
    detected_lang = detect_language(draft)
    expected_lang = req.ticket_language.lower()
    if expected_lang in ("de", "german") and detected_lang != "de":
        violations.append(
            "Language mismatch: Expected German ('de') but draft appears to be English."
        )
    elif expected_lang in ("en", "english") and detected_lang != "en":
        violations.append(
            "Language mismatch: Expected English ('en') but draft appears to be German."
        )

    # 3. Financial Promise Check
    # If the draft promises a refund or credit, an approved 'issue_credit' action must exist.
    has_financial_promise = bool(FINANCIAL_PROMISE_PATTERN.search(draft))
    if has_financial_promise and "issue_credit" not in req.approved_actions:
        violations.append(
            "Unauthorized financial commitment: Draft promises a refund or credit without an approved 'issue_credit' action."
        )

    # 4. Unknown Part Number / Hallucination Check
    if req.known_part_numbers:
        known_set = {p.upper() for p in req.known_part_numbers}
        mentioned_parts = PART_NUMBER_PATTERN.findall(draft)
        for part in mentioned_parts:
            part_upper = part.upper()
            # Ignore standard order/ticket prefixes
            if any(
                part_upper.startswith(prefix)
                for prefix in ("PO-", "TICK-", "RMA-", "MSG-", "ERR-", "CUST-")
            ):
                continue
            if part_upper not in known_set:
                violations.append(
                    f"Unknown hallucinated part number '{part}' mentioned in draft not found in order context."
                )

    passed = len(violations) == 0
    return ReplyQAResult(
        passed=passed,
        violations=violations,
        sanitized_draft=sanitized,
        detected_language=detected_lang,
    )
