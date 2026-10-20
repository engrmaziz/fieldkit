"""Outbound SMTP Dispatcher for Mailpit integration (Project 3 Milestone 5).

Sends MIME-compliant outbound emails to Halden customers via local Mailpit SMTP (port 1025).
Includes zero-dependency async execution and graceful offline fallback for test environments.
"""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage

from fieldkit_common.logging import get_logger
from pydantic import BaseModel

logger = get_logger("fieldkit.copilot.smtp")


class OutboundEmail(BaseModel):
    """Outbound customer email payload."""

    to_email: str
    subject: str
    body: str
    ticket_id: str
    sender: str = "support@halden-industrie.de"


class SendEmailResult(BaseModel):
    """Result of SMTP transmission."""

    success: bool
    ticket_id: str
    message_id: str
    recipient: str
    dispatched_at: str
    fallback_mode: bool = False
    error: str | None = None


class MailpitSMTPClient:
    """Async SMTP client dispatching messages to local Mailpit."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1025,
        timeout: float = 3.0,
        allow_mock: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.allow_mock = allow_mock

    def _sync_send(self, email: OutboundEmail, message_id: str) -> None:
        """Synchronous SMTP transmission executed in worker thread."""
        msg = EmailMessage()
        msg["From"] = email.sender
        msg["To"] = email.to_email
        msg["Subject"] = email.subject
        msg["Message-ID"] = f"<{message_id}@halden-industrie.de>"
        msg["X-Fieldkit-Ticket-ID"] = email.ticket_id
        msg["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg.set_content(email.body, charset="utf-8")

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            server.send_message(msg)

    async def send_email(self, email: OutboundEmail) -> SendEmailResult:
        """Transmit outbound email via Mailpit with automatic offline fallback."""
        message_id = f"MSG-{uuid.uuid4().hex[:12].upper()}"
        now_str = datetime.now(UTC).isoformat()

        try:
            await asyncio.to_thread(self._sync_send, email, message_id)
            logger.info(
                "Outbound email dispatched to Mailpit",
                ticket_id=email.ticket_id,
                recipient=email.to_email,
                message_id=message_id,
            )
            return SendEmailResult(
                success=True,
                ticket_id=email.ticket_id,
                message_id=message_id,
                recipient=email.to_email,
                dispatched_at=now_str,
                fallback_mode=False,
            )
        except Exception as exc:
            if self.allow_mock:
                logger.warning(
                    "Mailpit SMTP unreachable, using offline fallback",
                    ticket_id=email.ticket_id,
                    host=self.host,
                    port=self.port,
                    error=str(exc),
                )
                return SendEmailResult(
                    success=True,
                    ticket_id=email.ticket_id,
                    message_id=message_id,
                    recipient=email.to_email,
                    dispatched_at=now_str,
                    fallback_mode=True,
                )
            logger.error("Outbound SMTP dispatch failed", error=str(exc))
            return SendEmailResult(
                success=False,
                ticket_id=email.ticket_id,
                message_id=message_id,
                recipient=email.to_email,
                dispatched_at=now_str,
                fallback_mode=False,
                error=str(exc),
            )


_default_smtp_client: MailpitSMTPClient | None = None


def get_smtp_client() -> MailpitSMTPClient:
    """Return default singleton MailpitSMTPClient."""
    global _default_smtp_client
    if _default_smtp_client is None:
        _default_smtp_client = MailpitSMTPClient(host="localhost", port=1025, allow_mock=True)
    return _default_smtp_client
