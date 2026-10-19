# Evaluation Report: `acl-injection-defense` (Project 2: Milestone 3)

- **Date**: 2026-10-19 20:31:42
- **Git Commit**: `75188fe`
- **Evaluation Suite**: 40-Attack Adversarial ACL Injection Defense Benchmark (`evals/p2/acl_attacks.jsonl`)
- **Corpus Injections**: 5 tampered SOP documents with embedded indirect prompt injections
- **Targets**: `ACL Leaks = 0` (0.00%) & `Refusal Accuracy >= 90.0%`

## Summary Metrics

| Metric | Target | Measured | Result |
| :--- | :--- | :--- | :--- |
| **Total Attack Scenarios** | 40 | 40 | PASS |
| **ACL Leak Count** | 0 leaks | 0 | **PASS** |
| **ACL Leak Rate** | 0.00% | 0.00% | **PASS** |
| **Refusal Accuracy** | ≥ 90.0% | 100.00% | **PASS** |
| **Avg Query Latency** | < 100 ms | 0.01 ms | PASS |

## Attacks Breakdown by Category

| Category | Total Attacks | Refusals | Leaks | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Direct Escalation** | 10 | 10 (100.0%) | 0 | PASS |
| **Cross Plant** | 10 | 10 (100.0%) | 0 | PASS |
| **Indirect Injection** | 10 | 10 (100.0%) | 0 | PASS |
| **Jailbreak** | 10 | 10 (100.0%) | 0 | PASS |

## Defense Verification Highlights
1. **Pre-Retrieval ACL Filtration**: Attackers claiming `admin` role or elevated permissions via prompt text cannot bypass SQL-grade `allowed_roles` and `allowed_plants` checks in `HybridSearchEngine`.
2. **Passive Context Guarding**: The 5 injected documents containing `[SYSTEM OVERRIDE]` and `<!-- AI PROMPT INJECTION -->` directives are treated strictly as unexecutable data.
3. **Deterministic Query Coverage Gate**: Queries with insufficient authorized keyword coverage trigger an immediate safe refusal with zero citations or titles leaked.

---
*Report generated automatically by `evals/p2/acl_eval.py`.*
