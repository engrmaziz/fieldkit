"""Language detection and tsvector configuration mapping."""

import re

# Characteristic German stop-words & umlauts
GERMAN_MARKERS = {
    "der",
    "die",
    "das",
    "und",
    "für",
    "nicht",
    "mit",
    "bei",
    "oder",
    "ist",
    "von",
    "ein",
    "eine",
    "nach",
    "wird",
    "sind",
    "kann",
    "gemäß",
    "abschnitt",
    "druck",
    "ventil",
    "sicherheit",
    "hersteller",
}
GERMAN_CHARS = set("äöüßÄÖÜ")

# Characteristic Polish stop-words & diacritics
POLISH_MARKERS = {
    "i",
    "w",
    "na",
    "z",
    "do",
    "oraz",
    "jest",
    "przez",
    "przed",
    "dla",
    "jako",
    "przy",
    "od",
    "kontrola",
    "jakości",
    "zawór",
    "bezpieczeństwa",
    "zakład",
    "produkcyjny",
}
POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Characteristic English stop-words
ENGLISH_MARKERS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "which",
    "have",
    "shall",
    "must",
    "under",
    "regulation",
    "valve",
    "inspection",
    "requirements",
    "pressure",
    "operators",
}


def detect_document_language(text: str) -> str:
    """Detect document language (de, pl, en) based on token distribution and diacritics."""
    if not text or not text.strip():
        return "en"

    # Quick check for distinct character sets
    text_chars = set(text)
    german_char_hits = len(text_chars & GERMAN_CHARS)
    polish_char_hits = len(text_chars & POLISH_CHARS)

    tokens = [t.lower() for t in re.findall(r"\b\w+\b", text[:2000])]
    token_set = set(tokens)

    german_word_hits = len(token_set & GERMAN_MARKERS)
    polish_word_hits = len(token_set & POLISH_MARKERS)
    english_word_hits = len(token_set & ENGLISH_MARKERS)

    score_de = german_word_hits * 2 + german_char_hits * 3
    score_pl = polish_word_hits * 2 + polish_char_hits * 3
    score_en = english_word_hits * 2

    if score_de > score_en and score_de > score_pl:
        return "de"
    if score_pl > score_en and score_pl > score_de:
        return "pl"
    return "en"


def get_tsvector_config(language: str) -> str:
    """Map ISO language code to PostgreSQL tsvector text search dictionary."""
    mapping = {
        "de": "german",
        "en": "english",
        "pl": "simple",  # Postgres standard simple dictionary for Polish stemming
    }
    return mapping.get(language.lower(), "english")
