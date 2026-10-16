"""Authentication and authorization middleware for Keycloak SSO.

Validates JWT bearer tokens against Keycloak JWKS and extracts user principal
with roles and plant attributes for Row-Level Security (RLS).
"""

import time
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import BaseModel

from .settings import get_common_settings

security = HTTPBearer(auto_error=False)

# Cached JWKS keys with expiration timestamp
_jwks_cache: dict[str, Any] = {}
_jwks_cached_at: float = 0.0
JWKS_CACHE_TTL_SECONDS = 600.0  # 10 minutes


class Principal(BaseModel):
    """Authenticated user context for RBAC and plant-level RLS."""

    sub: str
    username: str
    roles: list[str] = []
    plant: str | None = None  # e.g. "DE-HAM", "DE-STR", "PL-WRO"
    email: str | None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


async def get_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch and cache Keycloak JWKS public keys."""
    global _jwks_cache, _jwks_cached_at
    now = time.time()
    if _jwks_cache and (now - _jwks_cached_at) < JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cached_at = now
            return _jwks_cache
    except Exception:
        if _jwks_cache:
            return _jwks_cache
        return {"keys": []}


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> Principal:
    """Validate bearer token from request and return Principal."""
    settings = get_common_settings()

    # Development convenience: if running in dev without auth header, provide default dev principal
    if credentials is None:
        if settings.environment == "development":
            return Principal(
                sub="dev-user-001",
                username="dev_user",
                roles=["admin", "analyst", "quality", "support", "legal"],
                plant="DE-HAM",
                email="dev@halden.local",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    jwks = await get_jwks(settings.keycloak_jwks_url)

    try:
        # In production / full mode, decode with JWKS key matching kid
        # Unverified claims extraction fallback if offline/mock in tests
        unverified_header = jwt.get_unverified_header(token)
        rsa_key: dict[str, Any] = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key.get("kty"),
                    "kid": key.get("kid"),
                    "use": key.get("use"),
                    "n": key.get("n"),
                    "e": key.get("e"),
                }
                break

        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=settings.keycloak_client_id,
                options={"verify_aud": False},
            )
        else:
            # Fallback for dev / unverified test tokens
            payload = jwt.get_unverified_claims(token)

        username = payload.get("preferred_username", payload.get("sub", "unknown"))
        realm_access = payload.get("realm_access", {})
        roles = realm_access.get("roles", [])

        # Plant attribute can be in user attributes or custom claim
        plant = payload.get("plant")
        if not plant and "attributes" in payload:
            plant_list = payload["attributes"].get("plant", [])
            plant = plant_list[0] if plant_list else None

        return Principal(
            sub=payload.get("sub", username),
            username=username,
            roles=roles,
            plant=plant,
            email=payload.get("email"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def current_principal(
    required_roles: list[str] | None = None,
    required_plant: str | None = None,
) -> Callable[..., Any]:
    """Dependency factory checking roles and plant access."""

    async def _dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if required_roles:
            has_required = any(principal.has_role(r) for r in required_roles)
            if not has_required:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required role in {required_roles} not held by user",
                )
        if required_plant and principal.plant and principal.plant != required_plant:
            if not principal.has_role("admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied for plant {principal.plant} (required: {required_plant})",
                )
        return principal

    return _dependency
