"""Deterministic synthetic corruption engine for Halden Industrie ERP data.

Simulates legacy data quality issues:
- OCR errors (rn/m, cl/d, vv/w, l/1, O/0)
- German umlauts and eszett (ae, ue, oe, ss)
- Legal form variations (GmbH, G.m.b.H., Gesellschaft mit beschrankter Haftung, Sp. z o.o.)
- Industrial abbreviations (Hydraulik -> Hydr., Maschinenbau -> Masch., etc.)
- Street abbreviations (Strasse -> Str., Weg -> Wg., Platz -> Pl.)
- Missing and transposed postcodes
- Swapped name/street lines
- All-caps names
"""

from __future__ import annotations

import random
import re
from typing import Any

# Umlaut constants using chr to avoid cross-platform encoding ambiguity
AE = chr(0xE4)
UE = chr(0xFC)
OE = chr(0xF6)
SZ = chr(0xDF)
CAP_AE = chr(0xC4)
CAP_UE = chr(0xDC)
CAP_OE = chr(0xD6)

# Bidirectional OCR character/digraph substitutions
OCR_PAIRS: list[tuple[str, str]] = [
    ("rn", "m"),
    ("cl", "d"),
    ("vv", "w"),
    ("l", "1"),
    ("O", "0"),
]

# Umlaut conversions
UMLAUT_MAP: list[tuple[str, str]] = [
    (AE, "ae"),
    (UE, "ue"),
    (OE, "oe"),
    (SZ, "ss"),
    (CAP_AE, "Ae"),
    (CAP_UE, "Ue"),
    (CAP_OE, "Oe"),
]

# Industrial word abbreviations
INDUSTRY_TERMS: list[tuple[str, str]] = [
    ("Hydraulik", "Hydr."),
    ("Maschinenbau", "Masch."),
    ("Industrie", "Ind."),
    ("Antriebstechnik", "Antriebst."),
    (f"Pr{AE}zisionstechnik", f"Pr{AE}zisionst."),
    ("Elektronik", "Elektr."),
    ("Komponenten", "Komp."),
    ("Werkzeugbau", "Werkzb."),
]

STRASSE_SZ = f"Stra{SZ}e"
STRASSE_SS = "Strasse"


def corrupt_ocr(text: str, rng: random.Random, rate: float = 0.08) -> str:
    """Substitutes visually confusing character pairs with given probability."""
    if not text:
        return text

    result = text
    for p1, p2 in OCR_PAIRS:
        if p1 in result and rng.random() < rate:
            result = result.replace(p1, p2, 1)
        elif p2 in result and rng.random() < rate:
            result = result.replace(p2, p1, 1)
    return result


def corrupt_umlauts(text: str, rng: random.Random, rate: float = 0.5) -> str:
    """Replaces umlauts with ascii expansions or vice-versa."""
    if not text:
        return text

    result = text
    for char, expanded in UMLAUT_MAP:
        if char in result and rng.random() < rate:
            result = result.replace(char, expanded)
        elif expanded in result and rng.random() < rate:
            result = result.replace(expanded, char)
    return result


def corrupt_industry_abbrev(text: str, rng: random.Random, rate: float = 0.4) -> str:
    """Expands or abbreviates industrial terms."""
    if not text or rng.random() >= rate:
        return text

    result = text
    for full, abbrev in INDUSTRY_TERMS:
        if full in result:
            return result.replace(full, abbrev)
        elif abbrev in result:
            return result.replace(abbrev, full)
    return result


def corrupt_street(street: str, rng: random.Random, rate: float = 0.5) -> str:
    """Standardizes or expands street abbreviations (including compound names)."""
    if not street or rng.random() >= rate:
        return street

    m_sz = re.search(rf"(?i)stra{SZ}e", street)
    if m_sz:
        rep = "str." if m_sz.group().islower() else "Str."
        if rng.random() < 0.5:
            rep = "strasse" if m_sz.group().islower() else "Strasse"
        return street[: m_sz.start()] + rep + street[m_sz.end() :]

    m_ss = re.search(r"(?i)strasse", street)
    if m_ss:
        rep = "str." if m_ss.group().islower() else "Str."
        if rng.random() < 0.5:
            rep = f"stra{SZ}e" if m_ss.group().islower() else f"Stra{SZ}e"
        return street[: m_ss.start()] + rep + street[m_ss.end() :]

    m_abbrev = re.search(r"(?i)str\.", street)
    if m_abbrev:
        target = f"stra{SZ}e" if m_abbrev.group().islower() else f"Stra{SZ}e"
        if rng.random() < 0.5:
            target = "strasse" if m_abbrev.group().islower() else "Strasse"
        return street[: m_abbrev.start()] + target + street[m_abbrev.end() :]

    if "Weg" in street:
        return street.replace("Weg", "Wg.")
    if "Wg." in street:
        return street.replace("Wg.", "Weg")
    if "Platz" in street:
        return street.replace("Platz", "Pl.")
    if "Pl." in street:
        return street.replace("Pl.", "Platz")
    if "Allee" in street:
        return street.replace("Allee", "All.")
    if "All." in street:
        return street.replace("All.", "Allee")
    return street


def corrupt_legal_form(name: str, rng: random.Random, country: str = "DE") -> str:
    """Mutates or normalizes the legal form suffix."""
    if not name:
        return name

    patterns = [
        (r"\b(GmbH & Co\.?\s*KG)\b", ["GmbH & Co. KG", "GmbH & Co KG", "GmbH u. Co. KG"]),
        (
            r"\b(GmbH|G\.m\.b\.H\.|Gesellschaft mit beschr[a\u00e4]nkter Haftung)\b",
            ["GmbH", "G.m.b.H.", f"Gesellschaft mit beschr{AE}nkter Haftung", "GmbH & Co. KG"],
        ),
        (r"\b(AG|A\.G\.|Aktiengesellschaft)\b", ["AG", "A.G.", "Aktiengesellschaft"]),
        (
            r"\b(Sp\.\s*z\s*o\.?\s*o\.?|Sp[o\u00f3][\u0142l]ka z o\.o\.)\b",
            ["Sp. z o.o.", f"Sp{chr(0xF3)}{chr(0x142)}ka z o.o.", "Sp. z o. o.", "Sp z o.o."],
        ),
    ]

    for regex, replacements in patterns:
        match = re.search(regex, name, re.IGNORECASE)
        if match:
            chosen = rng.choice(replacements)
            return re.sub(regex, chosen, name, count=1, flags=re.IGNORECASE)

    return name


def corrupt_postcode(
    postcode: str,
    rng: random.Random,
    missing_prob: float = 0.05,
    transpose_prob: float = 0.03,
) -> str:
    """Applies missing postcode or transposed digits corruption."""
    if not postcode:
        return ""

    if rng.random() < missing_prob:
        return ""

    digits = list(postcode.strip())
    if len(digits) >= 2 and rng.random() < transpose_prob:
        idx = rng.randint(0, len(digits) - 2)
        digits[idx], digits[idx + 1] = digits[idx + 1], digits[idx]
        return "".join(digits)

    return postcode


def corrupt_all_caps(name: str, rng: random.Random, prob: float = 0.10) -> str:
    """Converts company name to all caps with specified probability."""
    if not name:
        return name
    if rng.random() < prob:
        return name.upper()
    return name


def corrupt_name_street_swap(
    name: str,
    street: str,
    rng: random.Random,
    swap_prob: float = 0.01,
) -> tuple[str, str]:
    """Swaps name and street lines with small probability."""
    if rng.random() < swap_prob:
        return street, name
    return name, street


def apply_vendor_corruptions(
    record: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    """Applies a realistic suite of corruptions to a clean entity record."""
    name = record.get("legal_name", "")
    street = record.get("street", "")
    city = record.get("city", "")
    postcode = record.get("postcode", "")
    country = record.get("country", "DE")

    # 1. Legal form variation
    name = corrupt_legal_form(name, rng, country=country)

    # 2. Industry abbreviations
    name = corrupt_industry_abbrev(name, rng)

    # 3. Umlauts
    name = corrupt_umlauts(name, rng)
    city = corrupt_umlauts(city, rng)
    street = corrupt_umlauts(street, rng)

    # 4. Street syntax
    street = corrupt_street(street, rng)

    # 5. OCR confusion
    name = corrupt_ocr(name, rng, rate=0.08)
    street = corrupt_ocr(street, rng, rate=0.08)

    # 6. Postcode missing or transposed
    postcode = corrupt_postcode(postcode, rng)

    # 7. All-caps name
    name = corrupt_all_caps(name, rng, prob=0.10)

    # 8. Name and street swapped (1%)
    name, street = corrupt_name_street_swap(name, street, rng, swap_prob=0.01)

    return {
        **record,
        "legal_name": name,
        "street": street,
        "city": city,
        "postcode": postcode,
        "country": country,
    }
