"""Deterministic PII identification and masking for customer support tickets.

Prevents customer names, IBANs, phone numbers, and emails from leaking
into LLM prompts while preserving technical context (part numbers, error codes).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# Compiled regex patterns for industrial PII detection
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[\s-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}\b")
NAME_PATTERN = re.compile(
    r"\b(?:Herr|Frau|Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)\b"
)


class MaskedEntity(BaseModel):
    """Detected PII entity with span coordinates."""

    entity_type: str = Field(description="Category of PII: IBAN, EMAIL, PHONE, PERSON")
    original_value: str
    placeholder: str
    start: int
    end: int


class MaskingResult(BaseModel):
    """Result of PII masking operation."""

    masked_text: str
    detected_entities: list[MaskedEntity] = Field(default_factory=list)


def mask_pii(text: str) -> MaskingResult:
    """Mask sensitive PII entities in customer text with deterministic placeholders.

    Safeguards:
    - Leaves technical part numbers (e.g. HX-400, PO-1001, ERR-902) intact.
    - Masks personal identifiers (IBANs, names, phone numbers, emails).
    """
    detected: list[MaskedEntity] = []

    # 1. Mask IBANs
    for m in IBAN_PATTERN.finditer(text):
        detected.append(
            MaskedEntity(
                entity_type="IBAN",
                original_value=m.group(0),
                placeholder="[IBAN_REDACTED]",
                start=m.start(),
                end=m.end(),
            )
        )

    # 2. Mask Emails
    for m in EMAIL_PATTERN.finditer(text):
        detected.append(
            MaskedEntity(
                entity_type="EMAIL",
                original_value=m.group(0),
                placeholder="[EMAIL_REDACTED]",
                start=m.start(),
                end=m.end(),
            )
        )

    # 3. Mask Phones
    for m in PHONE_PATTERN.finditer(text):
        val = m.group(0)
        # Avoid masking part codes like PO-1001 or HX-400
        if not re.search(r"[A-Za-z]", val) and len(re.sub(r"\D", "", val)) >= 7:
            detected.append(
                MaskedEntity(
                    entity_type="PHONE",
                    original_value=val,
                    placeholder="[PHONE_REDACTED]",
                    start=m.start(),
                    end=m.end(),
                )
            )

    # 4. Mask Person Names following salutations
    for m in NAME_PATTERN.finditer(text):
        detected.append(
            MaskedEntity(
                entity_type="PERSON",
                original_value=m.group(0),
                placeholder="[PERSON_REDACTED]",
                start=m.start(),
                end=m.end(),
            )
        )

    # Sort detected entities in reverse order by start index to replace cleanly
    detected_sorted = sorted(detected, key=lambda x: x.start, reverse=True)
    masked = text
    for ent in detected_sorted:
        masked = masked[: ent.start] + ent.placeholder + masked[ent.end :]

    return MaskingResult(masked_text=masked, detected_entities=detected)
