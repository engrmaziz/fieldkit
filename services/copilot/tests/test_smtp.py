"""Unit tests for Outbound SMTP Dispatcher and Mailpit integration."""

from __future__ import annotations

import pytest
from fieldkit_copilot.smtp import MailpitSMTPClient, OutboundEmail


@pytest.mark.asyncio
async def test_email_construction() -> None:
    client = MailpitSMTPClient(host="localhost", port=1025, allow_mock=True)
    email = OutboundEmail(
        to_email="customer@example.de",
        subject="RMA Authorisation for Order PO-1001",
        body="Guten Tag, Ihre Rücksendung wurde genehmigt.",
        ticket_id="TICK-101",
    )
    result = await client.send_email(email)
    assert result.success is True
    assert result.message_id.startswith("MSG-")
    assert result.recipient == "customer@example.de"


@pytest.mark.asyncio
async def test_smtp_offline_graceful_fallback() -> None:
    # Point to an unused invalid port with allow_mock=True
    client = MailpitSMTPClient(host="127.0.0.1", port=65530, allow_mock=True)
    email = OutboundEmail(
        to_email="kunde@halden.de",
        subject="Status update",
        body="Vielen Dank für Ihre Anfrage.",
        ticket_id="TICK-102",
    )
    result = await client.send_email(email)
    assert result.success is True
    assert result.fallback_mode is True
    assert result.message_id.startswith("MSG-")
