# ADR 0002: Keycloak SSO Authentication, RBAC, and Plant-Level Row-Level Security (RLS)

- **Status**: Accepted
- **Date**: 2026-10-16
- **Author**: engrmaziz

## Context
Halden Industrie GmbH operates across three distinct manufacturing and assembly facilities:
- Hamburg (`DE-HAM`): HQ, Engineering, and Quality Management
- Stuttgart (`DE-STR`): Hydraulic Pump Operations & Support Center
- Wrocław (`PL-WRO`): Cylinder Machining & Supply Chain Logistics

Real enterprise customers do not accept ad-hoc API keys or insecure shared passwords; they mandate centralized Identity Provider (IdP) integration with Single Sign-On (SSO), granular Role-Based Access Control (RBAC), and strict data residency or plant-level segregation (Row-Level Security).

## Decision
1. **Centralized Identity Provider**: Deploy **Keycloak 26.1** in Docker Compose under the `core` profile, pre-seeded with realm `halden`.
2. **Client Architecture**:
   - `console`: Public client with PKCE (`S256` code challenge method) for the Next.js single-page application.
   - `api`: Bearer-only client for backend services to validate incoming access tokens.
3. **Role-Based Access Control (RBAC)**:
   - Six standard realm roles: `admin`, `analyst`, `quality`, `support`, `legal`, `viewer`.
   - `admin` possesses system-wide inspection rights and bypasses plant restrictions.
4. **Plant-Level Row-Level Security (RLS)**:
   - Every user account carries a `plant` attribute (`DE-HAM`, `DE-STR`, `PL-WRO`).
   - The shared middleware (`packages/common/fieldkit_common/auth.py`) decodes and verifies JWTs against Keycloak's JWKS endpoint (cached in-memory with a 10-minute TTL to eliminate network latency).
   - The dependency factory `current_principal(roles, plant)` enforces that users can only access records matching their assigned plant unless granted the `admin` role.

## Consequences
- **Positive**: Enterprise-ready SSO integration out of the box, automated pre-seeding via `halden-realm.json`, hardened token verification with JWKS caching, and enforceable plant partitioning.
- **Negative**: Adds ~500MB RAM footprint for the Keycloak JVM container in Compose.
