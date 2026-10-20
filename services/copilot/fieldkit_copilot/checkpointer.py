"""Checkpointer factory for LangGraph Ops Copilot state machine.

Provides persistence and state hydration across human interrupts:
- Uses PostgresSaver when PostgreSQL is online and accessible.
- Gracefully falls back to InMemorySaver when running unit tests or in offline environments.
"""

from __future__ import annotations

import os
from typing import Any

from fieldkit_common.logging import get_logger
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = get_logger("fieldkit.copilot.checkpointer")


def get_checkpointer(connection_string: str | None = None) -> BaseCheckpointSaver[Any]:
    """Return a checkpointer instance suitable for current runtime environment."""
    conn = connection_string or os.getenv(
        "DATABASE_URL",
        os.getenv(
            "POSTGRES_URI",
            "postgresql://fieldkit:fieldkit@localhost:5432/fieldkit",
        ),
    )

    # Attempt to connect to PostgreSQL if not explicitly disabled
    use_postgres = os.getenv("USE_POSTGRES_CHECKPOINTER", "false").lower() in ("1", "true")
    if use_postgres and conn:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool

            pool = ConnectionPool(conn, min_size=1, max_size=5, timeout=2.0)
            saver = PostgresSaver(pool)  # type: ignore[arg-type]
            saver.setup()
            logger.info("postgres_checkpointer_initialized", connection=conn)
            return saver
        except Exception as exc:
            logger.warning(
                "postgres_checkpointer_unavailable_fallback_to_memory",
                error=str(exc),
            )

    logger.info("in_memory_checkpointer_active")
    return MemorySaver()
