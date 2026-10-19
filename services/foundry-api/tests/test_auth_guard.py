"""Tests for authentication and authorization guards on Foundry API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal, current_principal
from fieldkit_foundry.db import get_db_session
from fieldkit_foundry.main import app
from fieldkit_ontology.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def auth_test_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_auth_guards(auth_test_db):
    async def override_get_db():
        async with auth_test_db() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    client = TestClient(app)

    # 1. Invalid Bearer Token returns 401 Unauthorized across all endpoints
    invalid_auth = {"Authorization": "Bearer invalid_malformed_jwt"}

    resp_obj = client.get("/objects/Supplier", headers=invalid_auth)
    assert resp_obj.status_code == 401

    resp_query = client.post(
        "/query", json={"type": "Supplier", "filters": []}, headers=invalid_auth
    )
    assert resp_query.status_code == 401

    resp_lineage = client.get(
        "/lineage/Supplier/00000000-0000-0000-0000-000000000000/name", headers=invalid_auth
    )
    assert resp_lineage.status_code == 401

    resp_review = client.get("/review-queue", headers=invalid_auth)
    assert resp_review.status_code == 401

    # 2. Role-based 403 Forbidden check: Principal with 'viewer' role accessing admin-only check
    guarded_dep = current_principal(required_roles=["admin"])
    viewer = Principal(sub="v1", username="viewer_user", roles=["viewer"], plant="DE-HAM")

    with pytest.raises(Exception) as exc_info:
        await guarded_dep(viewer)
    assert exc_info.value.status_code == 403

    app.dependency_overrides.clear()
