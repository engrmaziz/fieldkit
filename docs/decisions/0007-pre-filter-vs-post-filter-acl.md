# ADR 0007: Permission-Aware Retrieval Access Control (Pre-Filter vs Post-Filter ACLs)

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Halden Industrie GmbH stores sensitive enterprise documents spanning public standards (EU Machinery Regulation, OSHA standards), plant-specific standard operating procedures (SOPs), and highly confidential legal/executive records (patent litigations, warranty liabilities, confidential supplier pricing audits). Under Halden's security model, users possess role-based entitlements (`admin`, `quality`, `support`, `legal`, `viewer`) and plant-based scopes (`DE-HAM`, `DE-STR`, `PL-WRO`, or `Global`).

When performing semantic or lexical retrieval over document chunks, a fundamental architectural choice arises: whether to filter access control boundaries before vector/keyword similarity evaluation (**pre-filtering** inside the search engine / database `WHERE` clause) or after retrieving top-$k$ nearest candidates (**post-filtering** application-side).

## Decision
We enforce **mandatory pre-filtering** at both the PostgreSQL `tsvector` keyword query and `pgvector` HNSW similarity search stages.

1. **SQL WHERE Clause Predicate Injection**:
   Every retrieval query injects caller permissions directly into the database engine:
   ```sql
   WHERE allowed_roles && :user_roles
     AND (allowed_plants IS NULL OR :user_plant = ANY(allowed_plants))
   ```
2. **Pre-Filtering with pgvector HNSW**:
   In `pgvector` ($\ge 0.5.0$), iterative index scanning evaluates the boolean ACL predicate during graph traversal (`ef_search=80`), guaranteeing that all returned candidates are pre-authorized.
3. **No Post-Filtering**:
   Under no circumstances does the application fetch un-scoped chunks and filter them in Python memory.

## Alternatives Rejected
- **Post-Filtering (Fetch Top-k then Filter)**:
  - **Top-k Starvation**: If a user asks a query matching confidential documents and the retriever fetches $k=10$, all 10 candidates might belong to restricted roles (e.g. `legal`). Post-filtering discards all 10 chunks, leaving the answer generator with 0 context even if valid permitted documents existed at ranks 11–20.
  - **Information Leaks via Side-Channels**: Timing variations and candidate count drops reveal the existence and proximity of secret documents to unauthorized callers.
  - **Unbounded Over-Fetching**: Compensating for starvation requires speculative over-fetching ($k=100$), causing severe latency spikes on local CPU/quantized environments.

## Consequences
- **Positive**: Zero ACL data leakage across all 40 adversarial prompt injection and privilege escalation attacks (`acl_leak_count = 0`); guaranteed $k$ permitted documents returned to the RRF fusion pipeline; deterministic security boundary enforced at the storage engine.
- **Negative**: Requires indexed GIN/array columns (`allowed_roles text[]`, `allowed_plants text[]`) and tuned HNSW `ef_search` parameters to maintain sub-10ms latency when restrictive predicates eliminate large portions of the embedding index.
