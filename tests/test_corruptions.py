"""Unit tests for deterministic synthetic corruptions."""

import random

from scripts.corruptions import (
    SZ,
    UE,
    apply_vendor_corruptions,
    corrupt_all_caps,
    corrupt_industry_abbrev,
    corrupt_legal_form,
    corrupt_name_street_swap,
    corrupt_ocr,
    corrupt_postcode,
    corrupt_street,
    corrupt_umlauts,
)


def test_seed_determinism() -> None:
    """Verifies that two RNGs with the same seed generate identical outputs."""
    record = {
        "legal_name": f"M{UE}ller Hydraulik Maschinenbau GmbH & Co. KG",
        "street": f"Industriestra{SZ}e 42",
        "city": f"M{UE}nchen",
        "postcode": "80331",
        "country": "DE",
    }
    rng1 = random.Random(42)
    rng2 = random.Random(42)

    res1 = apply_vendor_corruptions(record, rng1)
    res2 = apply_vendor_corruptions(record, rng2)

    assert res1 == res2


def test_corrupt_ocr() -> None:
    """Verifies OCR character substitutions."""
    rng = random.Random(10)
    text = "clear modern"
    corrupted = corrupt_ocr(text, rng, rate=1.0)
    assert corrupted != text
    assert corrupt_ocr("", rng) == ""


def test_corrupt_umlauts() -> None:
    """Verifies German umlauts and eszett expansion."""
    rng = random.Random(7)
    text = f"M{UE}ller Gro{SZ}technik"
    res = corrupt_umlauts(text, rng, rate=1.0)
    assert "ue" in res or "ss" in res
    assert corrupt_umlauts("", rng) == ""


def test_corrupt_industry_abbrev() -> None:
    """Verifies abbreviation of industrial terms."""
    rng = random.Random(123)
    text = "Halden Hydraulik & Maschinenbau"
    res = corrupt_industry_abbrev(text, rng, rate=1.0)
    assert "Hydr." in res or "Masch." in res
    assert corrupt_industry_abbrev("", rng) == ""


def test_corrupt_street() -> None:
    """Verifies street abbreviations."""
    rng = random.Random(99)
    res = corrupt_street(f"Hauptstra{SZ}e 15", rng, rate=1.0)
    assert "str." in res.lower() or "strasse" in res.lower()
    assert corrupt_street("", rng) == ""


def test_corrupt_legal_form() -> None:
    """Verifies legal form mutation."""
    rng = random.Random(55)
    name_de = "Siemens AG"
    res_de = corrupt_legal_form(name_de, rng, country="DE")
    assert "Aktiengesellschaft" in res_de or "A.G." in res_de or res_de == "Siemens AG"

    name_pl = "Stalexport Sp. z o.o."
    res_pl = corrupt_legal_form(name_pl, rng, country="PL")
    assert "Sp" in res_pl


def test_corrupt_postcode() -> None:
    """Verifies missing postcodes and transposed digits."""
    rng = random.Random(42)
    assert corrupt_postcode("20095", rng, missing_prob=1.0) == ""

    transposed = corrupt_postcode("12345", rng, missing_prob=0.0, transpose_prob=1.0)
    assert len(transposed) == 5
    assert sorted(transposed) == sorted("12345")


def test_corrupt_all_caps() -> None:
    """Verifies all-caps name conversion."""
    rng = random.Random(42)
    assert corrupt_all_caps("Bosch Rexroth", rng, prob=1.0) == "BOSCH REXROTH"
    assert corrupt_all_caps("Bosch Rexroth", rng, prob=0.0) == "Bosch Rexroth"
    assert corrupt_all_caps("", rng) == ""


def test_corrupt_name_street_swap() -> None:
    """Verifies name and street swap under high swap prob."""
    rng = random.Random(42)
    name = "Acme Tools GmbH"
    street = f"Werkstra{SZ}e 1"

    s_name, s_street = corrupt_name_street_swap(name, street, rng, swap_prob=1.0)
    assert s_name == street
    assert s_street == name

    keep_name, keep_street = corrupt_name_street_swap(name, street, rng, swap_prob=0.0)
    assert keep_name == name
    assert keep_street == street


def test_apply_vendor_corruptions() -> None:
    """Verifies complete vendor corruptions preserve dictionary keys."""
    rng = random.Random(42)
    clean_record = {
        "lei": "529900T8BM49AURSDO55",
        "legal_name": f"Knorr-Bremse Systeme f{UE}r Nutzfahrzeuge GmbH",
        "street": f"Moosacher Stra{SZ}e 80",
        "city": f"M{UE}nchen",
        "postcode": "80809",
        "country": "DE",
    }
    corrupted = apply_vendor_corruptions(clean_record, rng)
    assert "legal_name" in corrupted
    assert "street" in corrupted
    assert "city" in corrupted
    assert "postcode" in corrupted
    assert "country" in corrupted
    assert corrupted["lei"] == clean_record["lei"]
