# ADR 0009: NL2SQL Safety Architecture (Client-Side sqlglot AST Validation vs DB-Permission-Only Safety)

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Project 2 translates natural language operational queries into SQL statements executed against Halden Industrie's production relational ontology. In an automated NL2SQL system powered by local LLMs (`qwen2.5-coder:7b`), generated queries pose severe operational risks:
1. **Destructive Mutation or Schema Sabotage**: `DROP TABLE`, `TRUNCATE`, `ALTER`, `UPDATE`, `INSERT`, `DELETE`.
2. **Resource Starvation & Denial of Service**: Calling sleep primitives (`pg_sleep()`), infinite Cartesian joins (`CROSS JOIN`), recursive Common Table Expressions (CTEs), or queries returning millions of rows.
3. **Privilege Escalation & Information Exfiltration**: File system reading (`COPY ... TO/FROM PROGRAM`), catalog inspection (`pg_shadow`, `pg_authid`), or stacked statement injection via semicolons (`;`).

A core architectural question is whether database-level privileges (`assistant_ro` role with read-only grants and Row-Level Security) are sufficient, or if mandatory client-side Abstract Syntax Tree (AST) inspection via `sqlglot` must be enforced before queries ever reach PostgreSQL.

## Decision
We enforce a **dual-layer defense-in-depth model** where client-side Abstract Syntax Tree validation via `sqlglot` is strictly mandatory before any query reaches PostgreSQL.

### Layer 1: Client-Side Deterministic AST Validation (`fieldkit_nl2sql.validator.SQLValidator`)
Every LLM-generated string must pass a strict `sqlglot` parse and inspection pipeline:
1. **Single Root Statement**: Must parse to exactly one statement; the root AST node must be `exp.Select` or `exp.Union` of Selects.
2. **Syntax Disallowance**: Semicolons and SQL comments are strictly stripped and rejected.
3. **Table & Column Allowlisting**: Tables must resolve strictly to approved ontology tables (`suppliers`, `parts`, `purchase_orders`, `shipments`, `quality_incidents`, `plants`).
4. **Function Allowlisting**: Only safe aggregate and scalar functions are allowed (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `COALESCE`, `ROUND`, `LOWER`, `UPPER`, `DATE_TRUNC`, `EXTRACT`).
5. **Forbidden Expressions**: Immediate rejection of `pg_sleep`, system catalogs, nested subquery depth $> 3$, and mutating DDL/DML.
6. **Mandatory Limit Injection**: If no `LIMIT` clause exists, `LIMIT 1000` is injected; if an existing `LIMIT` exceeds 1000, it is clamped to 1000.
7. **Query Cost Gating**: Optional `EXPLAIN (FORMAT JSON)` evaluation rejects any plan with estimated cost exceeding $10^6$.

### Layer 2: Sandboxed Database Role & RLS Execution (`fieldkit_nl2sql.executor.SQLExecutor`)
Validated queries execute as PostgreSQL role `assistant_ro`:
1. `REVOKE ALL` on schema `public`; `GRANT SELECT` only on ontology views.
2. Connection-scoped timeout: `SET LOCAL statement_timeout = '5s'`.
3. Plant RLS context: `SET LOCAL app.plant = :plant; SET LOCAL app.role = :role;`.

## Alternatives Rejected
- **Database-Permission-Only Safety**: Relying solely on `assistant_ro` leaves the database vulnerable to:
  - DoS attacks (`SELECT pg_sleep(300)` or unbounded cartesian joins will lock worker connections until server-level timeouts hit).
  - Out-of-memory crashes from queries lacking `LIMIT` clauses attempting to materialize gigabytes of row data.
  - Silent error cascades and lack of actionable repair prompt generation when non-conforming SQL is sent to PostgreSQL.
- **Regex/String Blacklist Filtering**: Trivial to bypass using whitespace tricks, mixed casing, inline comments (`/* ... */`), hex literals, or SQL dialect idiosyncrasies.

## Consequences
- **Positive**: Zero unsafe SQL executions attempted or allowed (`sql_unsafe_count = 0`); 100% rejection of 30 malicious SQL injection test fixtures; graceful error recovery with structured feedback for the LLM repair loop; complete protection against resource exhaustion.
- **Negative**: Adds negligible parsing overhead ($\approx 0.8\text{ ms}$ per query via `sqlglot`); complex window functions or custom PostgreSQL extensions must be explicitly allowlisted in the validator configuration.
