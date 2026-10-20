"""Unit tests for deterministic Outbound Reply QA Engine."""

from __future__ import annotations

from fieldkit_copilot.reply_qa import ReplyQARequest, validate_reply_qa


def test_reply_qa_valid_german() -> None:
    req = ReplyQARequest(
        ticket_id="TICK-101",
        ticket_language="de",
        ticket_text="Hydraulikventil HX-400 leckt Öl am Flansch. Bitte um Rückgabe.",
        reply_draft=(
            "Guten Tag, vielen Dank für Ihre Meldung zum Ventil HX-400. "
            "Wir haben Ihre Rücksendung autorisiert und senden Ihnen die Unterlagen."
        ),
        approved_actions=["create_rma"],
        known_part_numbers=["HX-400"],
    )
    result = validate_reply_qa(req)
    assert result.passed is True
    assert len(result.violations) == 0
    assert result.sanitized_draft == req.reply_draft


def test_reply_qa_valid_english() -> None:
    req = ReplyQARequest(
        ticket_id="TICK-102",
        ticket_language="en",
        ticket_text="Hydraulic cylinder seal leaking on assembly line. Need replacement part HX-400.",
        reply_draft=(
            "Hello, thank you for reaching out regarding part HX-400. "
            "We have initiated RMA processing and our logistics team will contact you shortly."
        ),
        approved_actions=["create_rma"],
        known_part_numbers=["HX-400"],
    )
    result = validate_reply_qa(req)
    assert result.passed is True
    assert len(result.violations) == 0


def test_reply_qa_detects_pii_leak() -> None:
    """Outbound replies must never leak unmasked customer IBANs or credit cards."""
    req = ReplyQARequest(
        ticket_id="TICK-103",
        ticket_language="de",
        ticket_text="Meine IBAN ist DE89370400440532013000.",
        reply_draft=(
            "Hallo, wir überweisen den Betrag an Ihre Bankverbindung DE89370400440532013000."
        ),
        approved_actions=["issue_credit"],
    )
    result = validate_reply_qa(req)
    assert result.passed is False
    assert any("PII" in v or "IBAN" in v for v in result.violations)
    # Sanitized version masks the leaked IBAN
    assert "DE89370400440532013000" not in result.sanitized_draft


def test_reply_qa_language_mismatch() -> None:
    """German customer tickets must receive German responses; English tickets English."""
    req = ReplyQARequest(
        ticket_id="TICK-104",
        ticket_language="de",
        ticket_text="Der Zylinder ist defekt.",
        reply_draft="Hello, thank you for contacting Halden customer support. We are checking this.",
        approved_actions=[],
    )
    result = validate_reply_qa(req)
    assert result.passed is False
    assert any("Language mismatch" in v for v in result.violations)


def test_reply_qa_unauthorized_financial_promise() -> None:
    """Outbound replies must not promise monetary refunds without an approved credit action."""
    req = ReplyQARequest(
        ticket_id="TICK-105",
        ticket_language="de",
        ticket_text="Wo bleibt mein Geld?",
        reply_draft="Guten Tag, wir erstatten Ihnen sofort 500 Euro auf Ihr Konto zurück.",
        approved_actions=[],  # No issue_credit approved!
    )
    result = validate_reply_qa(req)
    assert result.passed is False
    assert any(
        "financial commitment" in v.lower() or "refund" in v.lower() for v in result.violations
    )


def test_reply_qa_unknown_hallucinated_part_number() -> None:
    """Outbound replies must not hallucinate nonexistent part numbers."""
    req = ReplyQARequest(
        ticket_id="TICK-106",
        ticket_language="en",
        ticket_text="Need replacement for valve.",
        reply_draft="Hello, we are sending replacement part FAKE-9999 immediately.",
        approved_actions=["create_rma"],
        known_part_numbers=["HX-400", "HX-500"],
    )
    result = validate_reply_qa(req)
    assert result.passed is False
    assert any("FAKE-9999" in v for v in result.violations)
