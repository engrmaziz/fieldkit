# ADR 0005: Multi-Plant Data Isolation (PostgreSQL Row-Level Security vs Application-Level Filtering)

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Halden Industrie operates manufacturing plants in Hamburg (`DE-HAM`), Stuttgart (`DE-STR`), and Wroclaw (`PL-WRO`). German and European data governance policies require strict multi-tenant plant isolation: users assigned to a specific plant (such as quality engineers in Hamburg) must never be able to inspect, query, or infer procurement contracts, shipment status, or quality incidents originating from other plants, while central headquarters leadership requires global administrative visibility.

## Decision
We implemented a defense-in-depth isolation architecture combining PostgreSQL Row-Level Security (RLS) with application-layer query filtering:

1. **PostgreSQL Native Row-Level Security**:
   - `ENABLE ROW LEVEL SECURITY` activated on all plant-scoped tables (`suppliers`, `parts`, `purchase_orders`, `shipments`, `quality_incidents`).
   - Security Policy:
     ```sql
     CREATE POLICY plant_isolation_policy ON <table>
       FOR ALL
       USING (
         plant IS NULL
         OR plant = current_setting('app.plant', true)
         OR current_setting('app.role', true) = 'admin'
       );
     ```
   - Each FastAPI request session sets transaction-local variables inside the connection:
     `SELECT set_config('app.plant', :plant, true);`
     `SELECT set_config('app.role', :role, true);`
2. **Application-Level Defense-in-Depth (`apply_plant_rls`)**:
   - Every SQLAlchemy `Select` query compiled by the Typed Query DSL and graph traversal endpoints (`GET /objects/{type}/{id}/neighbors`) programmatically injects plant filtering.
   - Graph traversal boundaries: Neighbor entities discovered during multi-hop traversals (depth $\le 2$) must also satisfy the caller's plant RLS scope, preventing cross-plant data discovery through global supplier links.

## Alternatives Rejected
- **Application-Only Filtering**: High risk of catastrophic data leak if an endpoint misses a query filter or if analysts execute direct SQL queries against the database.
- **Physical Database per Plant**: Incompatible with cross-plant canonical entity resolution, global supplier spend analytics, and centralized Keycloak SSO authentication.

## Consequences
- **Positive**: Complete leak immunity (verified via `test_rls.py` proving `mehmet` cannot read Stuttgart rows even via raw SQL queries).
- **Negative**: Requires session context initialization on PostgreSQL connections; requires non-PostgreSQL engine detection (e.g. SQLite test runners) to avoid unsupported `set_config` calls.
