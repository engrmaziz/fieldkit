## Description
Briefly describe the purpose of this PR and what was changed.

## Rationale for Any New Dependencies
If new dependencies were added in `pyproject.toml` or `package.json`, explain why:
*(None or explain rationale)*

## Master Evaluation Suite Summary (Project 2 / Assistant)
> Paste the generated Summary Table from `evals/reports/assistant/<date>.md` here.

| Suite | Metric | Baseline | Target | Measured | Delta | Gate Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Retrieval** | Recall@10 (Hybrid+Rerank) | 94.17% | 90.00% | 94.17% | +0.00% | **PASS** |
| **Retrieval** | Recall@5 | 88.33% | - | 88.33% | +0.00% | **PASS** |
| **Retrieval** | Mean Reciprocal Rank (MRR) | 76.52% | - | 76.52% | +0.00% | **PASS** |
| **Answer** | Grounding / Faithfulness | 95.00% | 90.00% | 95.00% | +0.00% | **PASS** |
| **Answer** | Unanswerable Refusal Accuracy | 100.00% | 90.00% | 100.00% | +0.00% | **PASS** |
| **NL2SQL** | AST Safety Validity | 100.00% | 100.00% | 100.00% | +0.00% | **PASS** |
| **NL2SQL** | Execution Accuracy | 100.00% | 75.00% | 100.00% | +0.00% | **PASS** |
| **NL2SQL** | Unsafe SQL Executed (Zero Tolerance) | 0 | 0 | 0 | +0 | **PASS** |
| **Router** | Routing Accuracy (100 Q) | 96.00% | 92.00% | 96.00% | +0.00% | **PASS** |
| **ACL Defense** | Refusal Accuracy (40 Attacks) | 100.00% | 90.00% | 100.00% | +0.00% | **PASS** |
| **ACL Defense** | ACL Data Leaks (Zero Tolerance) | 0 | 0 | 0 | +0 | **PASS** |

## Quality & Regression Gate Checklist
- [ ] `make eval P=assistant` executed and passed cleanly.
- [ ] Zero ACL leaks detected (`acl_leak_count == 0`).
- [ ] Zero unsafe SQL executions attempted or allowed (`sql_unsafe_count == 0`).
- [ ] No accuracy or recall metric regressed by more than 2.0% vs `evals/p2/baseline.json`.
- [ ] Dated evaluation report committed under `evals/reports/assistant/<date>.md`.
- [ ] `make check` passed: 100% pytest tests green, Ruff clean, strict Mypy clean.
- [ ] No secrets or dataset artifacts committed.
