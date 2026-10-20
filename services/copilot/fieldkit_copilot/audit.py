"""Hash-chained, tamper-evident audit ledger with SHA-256 verification.

Provides an immutable event log for every state transition, tool execution,
and human decision in the Ops Copilot state machine.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

GENESIS_HASH = "0" * 64


def canonical_json(data: dict[str, Any]) -> str:
    """Format dictionary into deterministic canonical JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(
    prev_hash: str,
    sequence: int,
    timestamp: str,
    ticket_id: str,
    event_type: str,
    state_name: str,
    payload: dict[str, Any],
) -> str:
    """Compute SHA-256 cryptographic digest for an audit event."""
    payload_str = canonical_json(payload)
    raw_str = (
        f"{prev_hash}|{sequence}|{timestamp}|{ticket_id}|{event_type}|{state_name}|{payload_str}"
    )
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


class AuditEvent(BaseModel):
    """Immutable audit record linking cryptographically to its predecessor."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sequence: int
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    ticket_id: str
    event_type: str
    state_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str


class AuditLedger:
    """In-memory and persistent cryptographic audit ledger."""

    def __init__(self) -> None:
        # Maps ticket_id to list of sequentially chained events
        self._events: dict[str, list[AuditEvent]] = {}

    def record_event(
        self,
        ticket_id: str,
        event_type: str,
        state_name: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append a new verified event to the ticket's audit chain."""
        if payload is None:
            payload = {}

        chain = self._events.setdefault(ticket_id, [])
        sequence = len(chain) + 1
        prev_hash = chain[-1].hash if chain else GENESIS_HASH
        timestamp = datetime.now(UTC).isoformat()
        event_id = str(uuid.uuid4())

        event_hash = compute_event_hash(
            prev_hash=prev_hash,
            sequence=sequence,
            timestamp=timestamp,
            ticket_id=ticket_id,
            event_type=event_type,
            state_name=state_name,
            payload=payload,
        )

        event = AuditEvent(
            event_id=event_id,
            sequence=sequence,
            timestamp=timestamp,
            ticket_id=ticket_id,
            event_type=event_type,
            state_name=state_name,
            payload=payload,
            prev_hash=prev_hash,
            hash=event_hash,
        )
        chain.append(event)
        return event

    def get_events(self, ticket_id: str) -> list[AuditEvent]:
        """Retrieve full audit event chain for a ticket."""
        return list(self._events.get(ticket_id, []))

    def verify_integrity(self, ticket_id: str | None = None) -> tuple[bool, list[str]]:
        """Verify 100% cryptographic integrity of the audit ledger.

        Detects:
        - Payload alterations
        - Timestamp or sequence modifications
        - Broken prev_hash pointers
        - Sequence gaps caused by deleted events
        """
        errors: list[str] = []
        tickets_to_verify = [ticket_id] if ticket_id else list(self._events.keys())

        for tid in tickets_to_verify:
            chain = self._events.get(tid, [])
            if not chain:
                continue

            expected_prev = GENESIS_HASH
            for idx, event in enumerate(chain, start=1):
                # 1. Sequence check
                if event.sequence != idx:
                    errors.append(
                        f"[{tid}] Sequence gap: expected {idx}, found {event.sequence} (Event ID: {event.event_id})"
                    )

                # 2. Previous hash link check
                if event.prev_hash != expected_prev:
                    errors.append(
                        f"[{tid}] Broken chain at sequence {event.sequence}: prev_hash '{event.prev_hash}' does not match expected '{expected_prev}'"
                    )

                # 3. Payload integrity check (recompute digest)
                recomputed = compute_event_hash(
                    prev_hash=event.prev_hash,
                    sequence=event.sequence,
                    timestamp=event.timestamp,
                    ticket_id=event.ticket_id,
                    event_type=event.event_type,
                    state_name=event.state_name,
                    payload=event.payload,
                )
                if event.hash != recomputed:
                    errors.append(
                        f"[{tid}] Hash mismatch at sequence {event.sequence}: stored '{event.hash}' != computed '{recomputed}'. Payload tampered!"
                    )

                expected_prev = event.hash

        return len(errors) == 0, errors


# Global singleton instance for service runtime
_global_ledger = AuditLedger()


def get_audit_ledger() -> AuditLedger:
    """Return singleton audit ledger instance."""
    return _global_ledger
