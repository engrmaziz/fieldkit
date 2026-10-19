"""Integration tests for keyset pagination, text search, and root /query endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_foundry.db import get_db_session
from fieldkit_foundry.main import app
from fieldkit_ontology.models import Base, Supplier
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def search_test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    base_time = datetime.now(UTC)
    suppliers = []
    names = [
        "Krupp Hydraulik AG",
        "Müller Ventilbau GmbH",
        "Krupp Dichtungen GmbH",
        "Bosch Rexroth AG",
        "Halden Hydraulics GmbH",
    ]

    async with session_maker() as session:
        for idx, name in enumerate(names):
            sup = Supplier(
                id=uuid.uuid4(),
                natural_key=f"sup_{idx}",
                supplier_code=f"sup_{idx}",
                name=name,
                country="DE",
                plant=None,
                row_hash=f"h_{idx}",
                created_run_id="run_1",
                updated_run_id="run_1",
                created_at=base_time - timedelta(minutes=idx * 5),
                updated_at=base_time - timedelta(minutes=idx * 5),
            )
            suppliers.append(sup)
        session.add_all(suppliers)
        await session.commit()

    yield session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_keyset_pagination_and_search(search_test_session):
    async def override_get_db():
        async with search_test_session() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="jana_id",
        username="jana",
        roles=["admin"],
        plant="DE-HAM",
    )

    client = TestClient(app)

    # 1. First page: limit 2
    resp_p1 = client.get("/objects/Supplier?limit=2")
    assert resp_p1.status_code == 200
    p1_data = resp_p1.json()
    assert p1_data["count"] == 2
    assert p1_data["next_cursor"] is not None

    # 2. Second page: limit 2 with cursor
    cursor_1 = p1_data["next_cursor"]
    resp_p2 = client.get(f"/objects/Supplier?limit=2&cursor={cursor_1}")
    assert resp_p2.status_code == 200
    p2_data = resp_p2.json()
    assert p2_data["count"] == 2
    assert p2_data["next_cursor"] is not None

    # Verify no item overlap between pages
    p1_ids = {item["id"] for item in p1_data["items"]}
    p2_ids = {item["id"] for item in p2_data["items"]}
    assert p1_ids.isdisjoint(p2_ids)

    # 3. Third page: remaining 1 item
    cursor_2 = p2_data["next_cursor"]
    resp_p3 = client.get(f"/objects/Supplier?limit=2&cursor={cursor_2}")
    assert resp_p3.status_code == 200
    p3_data = resp_p3.json()
    assert p3_data["count"] == 1
    assert p3_data["next_cursor"] is None

    # 4. Search query '?q=Krupp'
    resp_search = client.get("/objects/Supplier?q=Krupp")
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert search_data["count"] == 2
    for item in search_data["items"]:
        assert "Krupp" in item["name"]

    # 5. Root POST /query endpoint execution
    resp_query = client.post(
        "/query",
        json={
            "type": "Supplier",
            "filters": [{"prop": "name", "op": "contains", "value": "Rexroth"}],
            "limit": 10,
        },
    )
    assert resp_query.status_code == 200
    q_res = resp_query.json()
    assert q_res["count"] == 1
    assert "Bosch Rexroth" in q_res["items"][0]["name"]

    app.dependency_overrides.clear()
