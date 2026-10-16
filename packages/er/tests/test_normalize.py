"""Tests for supplier entity resolution normalization functions, including Hypothesis property tests."""

from __future__ import annotations

from fieldkit_er.normalize import create_match_key, normalize_name, normalize_street, normalize_text
from hypothesis import given, settings
from hypothesis import strategies as st


def test_normalize_umlauts() -> None:
    assert "mueller" in normalize_text("Müller")
    assert "oel" in normalize_text("Öl")
    assert "baer" in normalize_text("Bär")
    assert "weiss" in normalize_text("Weiß")


def test_normalize_legal_forms_de() -> None:
    assert normalize_name("Müller Hydraulik GmbH") == "mueller hydraulik"
    assert normalize_name("Mueller Hydraulik G.m.b.H.") == "mueller hydraulik"
    assert normalize_name("MUELLER HYDRAULIK GMBH & CO. KG") == "mueller hydraulik"
    assert normalize_name("Siemens AG") == "siemens"
    assert normalize_name("Krupp AG & Co. KGaA") == "krupp"


def test_normalize_legal_forms_pl_cz() -> None:
    assert normalize_name("Pol-Stahl Sp. z o.o.") == "pol stahl"
    assert normalize_name("Armatura Spółka Akcyjna") == "armatura"
    assert normalize_name("Bohemia Trade s.r.o.") == "bohemia trade"
    assert normalize_name("Praga Metal a.s.") == "praga metal"


def test_normalize_abbreviations() -> None:
    assert normalize_name("Mueller Hydr. GmbH") == "mueller hydraulik"
    assert normalize_name("Nord Ind. Werk") == "nord industrie werk"
    assert normalize_street("Hauptstr. 42") == "hauptstrasse 42"
    assert normalize_street("Berliner Straße 10") == "berliner strasse 10"


def test_create_match_key() -> None:
    k1 = create_match_key("Müller Hydraulik GmbH", "Industriestr. 5", "Hamburg")
    k2 = create_match_key("Mueller Hydr. G.m.b.H.", "Industriestrasse 5", "Hamburg")
    assert k1 == k2


# Property-based testing with Hypothesis
@given(st.text())
@settings(max_examples=100)
def test_normalize_text_never_crashes(text: str) -> None:
    # Must never crash on arbitrary unicode strings
    result = normalize_text(text)
    assert isinstance(result, str)


@given(st.text())
@settings(max_examples=100)
def test_normalize_text_is_idempotent(text: str) -> None:
    # Property: f(f(x)) == f(x)
    once = normalize_text(text)
    twice = normalize_text(once)
    assert once == twice
