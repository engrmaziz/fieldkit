"""Deterministic Supplier Normalization Engine for Entity Resolution.

Performs:
- Unicode NFKC normalization
- Casefolding
- Umlaut expansion (ü->ue, ö->oe, ä->ae, ß->ss)
- Legal form stripping for DE/AT/PL/CZ
- Domain abbreviation expansion (Str.->strasse, Hydr.->hydraulik, etc.)
- Match key extraction without mutating original raw records.
"""

from __future__ import annotations

import re
import unicodedata

# Legal forms sorted longest first to prevent partial prefix/suffix stripping
LEGAL_FORMS_PATTERN = re.compile(
    r"(?:\b)("
    # German / Austrian forms
    r"gmbh\s*&\s*co\.?\s*kgaa|"
    r"gmbh\s*&\s*co\.?\s*kg|"
    r"gmbh\s*&\s*co\.?|"
    r"g\.?\s*m\.?\s*b\.?\s*h\.?|"
    r"gmbh|"
    r"ag\s*&\s*co\.?\s*kgaa|"
    r"ag\s*&\s*co\.?\s*kg|"
    r"a\.?\s*g\.?|"
    r"ag|"
    r"k\.?\s*g\.?|"
    r"kg|"
    r"kgaa|"
    r"e\.?\s*v\.?|"
    r"o\.?\s*h\.?\s*g\.?|"
    r"ohg|"
    r"gbr|"
    r"ug\s*\([^)]*\)|"
    r"ug|"
    # Polish forms
    r"spółka\s+akcyjna|"
    r"spolka\s+akcyjna|"
    r"spółka\s+z\s+o\.o\.|"
    r"spolka\s+z\s+o\.o\.|"
    r"sp\.\s*z\s*o\.?\s*o\.?|"
    r"sp\.\s*k\.|"
    r"sp\.\s*j\.|"
    r"s\.?\s*a\.?|"
    # Czech forms
    r"spol\.\s*s\s*r\.?\s*o\.?|"
    r"s\.?\s*r\.?\s*o\.?|"
    r"a\.?\s*s\.?|"
    r"v\.?\s*o\.?\s*s\.?|"
    r"k\.?\s*s\.?"
    r")(?=\s|[^\w]|$)",
    re.IGNORECASE,
)

ABBREVIATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bhydr\.?(?=\s|[^\w]|$)", re.IGNORECASE), "hydraulik"),
    (re.compile(r"\bmasch\.?(?=\s|[^\w]|$)", re.IGNORECASE), "maschinen"),
    (re.compile(r"\bind\.?(?=\s|[^\w]|$)", re.IGNORECASE), "industrie"),
    (re.compile(r"\belektr\.?(?=\s|[^\w]|$)", re.IGNORECASE), "elektronik"),
    (re.compile(r"\belektro\.?(?=\s|[^\w]|$)", re.IGNORECASE), "elektronik"),
    (re.compile(r"\bwerkzeugmasch\.?(?=\s|[^\w]|$)", re.IGNORECASE), "werkzeugmaschinen"),
]


def normalize_text(text: str | None) -> str:
    """Performs Unicode NFKC normalization, lowercase casefold, umlaut folding, and whitespace collapse."""
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    s = unicodedata.normalize("NFKC", str(text))

    # 2. Casefold
    s = s.casefold()

    # 3. Umlauts & special characters folding
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")

    # 4. Collapse whitespace
    s = " ".join(s.split())
    return s


def normalize_name(name: str | None) -> str:
    """Normalizes company/supplier name by stripping legal forms and expanding abbreviations."""
    s = normalize_text(name)
    if not s:
        return ""

    # Expand common domain abbreviations
    for pattern, replacement in ABBREVIATIONS:
        s = pattern.sub(replacement, s)

    # Strip legal forms
    s = LEGAL_FORMS_PATTERN.sub(" ", s)

    # Clean non-alphanumeric punctuation to single space
    s = re.sub(r"[^\w\s]", " ", s)

    # Collapse multiple whitespaces and strip
    s = " ".join(s.split())
    return s


def normalize_street(street: str | None) -> str:
    """Normalizes street address and expands standard address abbreviations."""
    s = normalize_text(street)
    if not s:
        return ""

    # Replace compound and standalone street abbreviations
    s = re.sub(r"(str\.|straße\b|strasse\b|\bstr\b|str\b)", "strasse", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpl\.?\b", "platz", s, flags=re.IGNORECASE)
    s = re.sub(r"\bdr\.?\b", "doktor", s, flags=re.IGNORECASE)

    # Clean unnecessary punctuation (leave alphanumeric numbers intact)
    s = re.sub(r"[^\w\s]", " ", s)
    s = " ".join(s.split())
    return s


def create_match_key(name: str | None, street: str | None = None, city: str | None = None) -> str:
    """Generates canonical match key for blocking and fast indexing."""
    n_clean = normalize_name(name)
    parts = [n_clean]

    if street:
        st_clean = normalize_street(street)
        if st_clean:
            parts.append(st_clean)

    if city:
        c_clean = normalize_text(city)
        if c_clean:
            parts.append(c_clean)

    return " | ".join(parts)
