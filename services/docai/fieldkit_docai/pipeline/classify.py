"""Magic-byte document verification and type classification."""

from __future__ import annotations

import re

from fieldkit_docai.models import DocumentType


class DocumentTypeException(ValueError):
    """Raised when an uploaded file violates supported MIME types or magic byte headers."""

    pass


# Magic byte signatures
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF-"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/tiff": [b"II*\x00", b"MM\x00*"],
}


def detect_mime_type(content: bytes) -> str | None:
    """Identify MIME type from header magic bytes."""
    if not content or len(content) < 4:
        return None

    for mime, signatures in MAGIC_SIGNATURES.items():
        for sig in signatures:
            if content.startswith(sig):
                return mime
    return None


def validate_magic_bytes(content: bytes) -> str:
    """Validate that uploaded content starts with valid magic bytes for PDF/PNG/JPEG/TIFF.

    Raises:
        DocumentTypeException: If content is empty or starts with invalid/unsupported magic bytes.
    """
    if not content:
        raise DocumentTypeException("Uploaded file is empty (0 bytes)")

    mime = detect_mime_type(content)
    if mime is None:
        raise DocumentTypeException(
            f"Unsupported or invalid document magic bytes: file starts with {content[:8]!r}. "
            "Supported formats: PDF (%PDF-), PNG (\\x89PNG), JPEG (\\xff\\xd8\\xff), TIFF (II* / MM*)."
        )
    return mime


def classify_document_type(text: str, filename: str) -> DocumentType:
    """Classify document type using deterministic domain heuristics on text content and filename."""
    combined = f"{filename} {text}".lower()

    # Delivery note patterns
    delivery_patterns = [
        r"\blieferschein\b",
        r"\bdelivery\s+note\b",
        r"\bpacking\s+slip\b",
        r"\bwareneingang\b",
        r"\bpackliste\b",
        r"\bfrachtbrief\b",
        r"\bls-\d{4}\b",
    ]
    if any(re.search(pat, combined) for pat in delivery_patterns):
        return DocumentType.DELIVERY_NOTE

    # Contract patterns
    contract_patterns = [
        r"\bvertrag\b",
        r"\bagreement\b",
        r"\bcontract\b",
        r"\bnda\b",
        r"\bconfidentiality\b",
        r"\bliability\s+cap\b",
        r"\bgoverning\s+law\b",
        r"\bhausratsversicherung\b",
        r"\bgewährleistung\b",
        r"\bterms\s+and\s+conditions\b",
        r"\bparties\s+agree\b",
        r"\barticle\s+\d+\b",
        r"\b§\s*\d+\b",
    ]
    if any(re.search(pat, combined) for pat in contract_patterns):
        return DocumentType.CONTRACT

    return DocumentType.OTHER
