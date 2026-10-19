"""Exact-match response cache keyed by normalized query, principal scope, and index version."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from fieldkit_common.auth import Principal


def compute_cache_key(
    query: str,
    principal: Principal,
    index_version: str = "v1",
) -> str:
    """Compute deterministic SHA-256 cache key."""
    # Normalize: lowercase, strip punctuation, single whitespace
    normalized_q = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", query.lower())).strip()
    roles_str = ",".join(sorted(principal.roles))
    plant_str = principal.plant or "all"
    scope_repr = f"roles={roles_str}|plant={plant_str}"
    raw = f"{normalized_q}::{scope_repr}::{index_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ResponseCache:
    """In-memory response cache with TTL expiration and scope isolation."""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self.default_ttl = default_ttl_seconds
        # key -> (expiry_time, cached_data)
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve unexpired entry, or None."""
        if key not in self._cache:
            return None
        expires_at, data = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        return data

    def set(self, key: str, data: dict[str, Any], ttl_seconds: float | int | None = None) -> None:
        """Store entry with TTL."""
        ttl = float(ttl_seconds) if ttl_seconds is not None else float(self.default_ttl)
        self._cache[key] = (time.time() + ttl, data)

    def invalidate(self, key: str) -> bool:
        """Remove single entry."""
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of active keys."""
        now = time.time()
        # Clean expired
        expired = [k for k, (exp, _) in self._cache.items() if now > exp]
        for k in expired:
            del self._cache[k]
        return len(self._cache)
