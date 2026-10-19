"""Database Session Management and Postgres RLS Context."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from fieldkit_common.auth import Principal
from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fieldkit",
)

# Convert standard postgres:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def set_rls_context(session: AsyncSession, principal: Principal | None) -> None:
    """Sets PostgreSQL session variables for Row-Level Security inside transaction."""
    if not principal:
        return

    # Skip set_config on non-Postgres engines (e.g. SQLite) to avoid exception overhead
    bind = session.bind
    if bind is not None and getattr(bind.dialect, "name", "") != "postgresql":
        return

    plant_val = principal.plant or ""
    role_val = principal.roles[0] if principal.roles else "viewer"

    # Use Postgres set_config(setting_name, new_value, is_local)
    try:
        await session.execute(
            text("SELECT set_config('app.plant', :plant, true);"),
            {"plant": plant_val},
        )
        await session.execute(
            text("SELECT set_config('app.role', :role, true);"),
            {"role": role_val},
        )
    except Exception:
        # Fallback for non-Postgres / test environments
        pass


def apply_plant_rls(
    query: Select[Any],
    model: Any,
    principal: Principal,
) -> Select[Any]:
    """Defense-in-depth application-layer filter mirroring Postgres RLS policy."""
    if principal.has_role("admin"):
        return query

    if hasattr(model, "plant"):
        return query.where((model.plant.is_(None)) | (model.plant == principal.plant))
    return query


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding database session."""
    async with async_session_factory() as session:
        yield session
