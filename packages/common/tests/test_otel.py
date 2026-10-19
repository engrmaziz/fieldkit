"""Unit tests for OpenTelemetry utilities and PII masking in fieldkit_common."""

from fieldkit_common.otel import (
    get_tracer,
    init_tracer,
    mask_pii,
    sanitize_and_truncate,
)


def test_mask_pii_email() -> None:
    text = "Please send the hydraulic cylinder order to jana.weber@halden-industrie.de immediately."
    masked = mask_pii(text)
    assert "[EMAIL]" in masked
    assert "jana.weber@halden-industrie.de" not in masked
    assert "hydraulic cylinder order" in masked


def test_mask_pii_iban() -> None:
    text = "Halden bank details for wire transfer: DE89370400440532013000 at Deutsche Bank."
    masked = mask_pii(text)
    assert "[IBAN]" in masked
    assert "DE89370400440532013000" not in masked


def test_mask_pii_phone() -> None:
    text = "Emergency plant maintenance line is +49 40 12345678 or call 040-98765432."
    masked = mask_pii(text)
    assert "[PHONE]" in masked
    assert "+49 40 12345678" not in masked


def test_mask_pii_credit_card() -> None:
    text = "Charged corporate card 4532-1234-5678-9012 for expediting delivery."
    masked = mask_pii(text)
    assert "[CREDIT_CARD]" in masked
    assert "4532-1234-5678-9012" not in masked


def test_sanitize_and_truncate() -> None:
    long_text = "Important info: user@test.com. " + ("A" * 5000)
    sanitized = sanitize_and_truncate(long_text, max_bytes=100)
    assert "[EMAIL]" in sanitized
    assert len(sanitized.encode("utf-8")) <= 100 + len("... [truncated]")
    assert sanitized.endswith("... [truncated]")


def test_init_tracer_resource_attributes() -> None:
    tracer = init_tracer(
        service_name="test-service",
        version="1.2.3",
        environment="test",
        endpoint=None,
    )
    assert tracer is not None
    assert get_tracer("test-service") is not None
