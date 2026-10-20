"""Unit tests for deterministic PII masking in support copilot."""

from fieldkit_copilot.pii import mask_pii


def test_mask_pii_german_customer_ticket() -> None:
    raw_text = (
        "Guten Tag, hier spricht Herr Klaus Weber. "
        "Unsere Pumpe HX-400 zu Bestellung PO-1001 leckt stark. "
        "Bitte erstatten Sie den Betrag auf DE89370400440532013000 oder rufen Sie unter +49 171 2345678 an. "
        "Meine E-Mail ist klaus.weber@industrial-de.com."
    )
    result = mask_pii(raw_text)
    masked = result.masked_text

    # Verify PII is masked
    assert "DE89370400440532013000" not in masked
    assert "[IBAN_REDACTED]" in masked
    assert "klaus.weber@industrial-de.com" not in masked
    assert "[EMAIL_REDACTED]" in masked
    assert "+49 171 2345678" not in masked
    assert "[PHONE_REDACTED]" in masked
    assert "Herr Klaus Weber" not in masked
    assert "[PERSON_REDACTED]" in masked

    # Verify technical identifiers remain intact
    assert "HX-400" in masked
    assert "PO-1001" in masked


def test_mask_pii_clean_ticket() -> None:
    raw_text = "Die Lieferung zu PO-1002 ist verspätet. Sendungsnummer DHL-992381."
    result = mask_pii(raw_text)
    assert result.masked_text == raw_text
    assert len(result.detected_entities) == 0
