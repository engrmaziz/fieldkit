"""Unit tests for Keycloak auth and RLS enforcement."""

import pytest
import respx
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from fieldkit_common.auth import (
    Principal,
    current_principal,
    get_jwks,
)

app = FastAPI()


@app.get("/guarded-role")
async def guarded_role(
    principal: Principal = pytest.importorskip("fastapi").Depends(
        current_principal(required_roles=["quality"])
    ),
) -> dict[str, str]:
    return {"user": principal.username, "plant": principal.plant or ""}


@app.get("/guarded-plant")
async def guarded_plant(
    principal: Principal = pytest.importorskip("fastapi").Depends(
        current_principal(required_plant="DE-HAM")
    ),
) -> dict[str, str]:
    return {"user": principal.username, "plant": principal.plant or ""}


client = TestClient(app)


def test_principal_role_check() -> None:
    user = Principal(sub="1", username="mehmet", roles=["quality"], plant="DE-HAM")
    assert user.has_role("quality") is True
    assert user.has_role("admin") is False

    admin = Principal(sub="2", username="jana", roles=["admin"], plant="DE-HAM")
    assert admin.has_role("quality") is True  # Admin inherits all roles
    assert admin.has_role("legal") is True


@pytest.mark.asyncio
@respx.mock
async def test_jwks_caching_10_minutes() -> None:
    jwks_url = "http://localhost:8080/realms/halden/protocol/openid-connect/certs"
    route = respx.get(jwks_url).respond(
        status_code=200,
        json={"keys": [{"kid": "test-kid", "kty": "RSA"}]},
    )

    # First fetch hits HTTP
    jwks1 = await get_jwks(jwks_url)
    assert route.call_count == 1
    assert jwks1["keys"][0]["kid"] == "test-kid"

    # Second fetch should hit memory cache (TTL is 10 min = 600s)
    jwks2 = await get_jwks(jwks_url)
    assert route.call_count == 1
    assert jwks2 == jwks1


@pytest.mark.asyncio
async def test_current_principal_dependency_role_allowed() -> None:
    dep = current_principal(required_roles=["quality"])
    mehmet = Principal(sub="1", username="mehmet", roles=["quality"], plant="DE-HAM")
    result = await dep(mehmet)
    assert result.username == "mehmet"


@pytest.mark.asyncio
async def test_current_principal_dependency_role_forbidden() -> None:
    dep = current_principal(required_roles=["quality"])
    lukas = Principal(sub="2", username="lukas", roles=["support"], plant="DE-STR")
    with pytest.raises(HTTPException) as exc_info:
        await dep(lukas)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_current_principal_dependency_plant_rls() -> None:
    dep = current_principal(required_plant="DE-HAM")

    # Allowed: Mehmet is at DE-HAM
    mehmet = Principal(sub="1", username="mehmet", roles=["quality"], plant="DE-HAM")
    res = await dep(mehmet)
    assert res.plant == "DE-HAM"

    # Forbidden: Lukas is at DE-STR
    lukas = Principal(sub="2", username="lukas", roles=["support"], plant="DE-STR")
    with pytest.raises(HTTPException) as exc_info:
        await dep(lukas)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    # Admin bypass: Jana is admin, can access DE-HAM even if plant is omitted or different
    jana = Principal(sub="3", username="jana", roles=["admin"], plant="PL-WRO")
    admin_res = await dep(jana)
    assert admin_res.username == "jana"
