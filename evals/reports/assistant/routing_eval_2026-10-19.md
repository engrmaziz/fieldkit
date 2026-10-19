# Evaluation Report: `routing-core` (Project 2: Milestone 5)

> **Evaluated Model**: Hybrid Query Router (`fieldkit_assistant.router.HybridRouter`)
> **Date**: 2026-10-19
> **Target Accuracy**: $\ge 90.0\%$
> **Dataset**: `evals/p2/routing_gold.jsonl` (100 labeled queries)

---

## 1. Executive Summary

| Metric | Target | Measured | Result |
| :--- | :--- | :--- | :--- |
| **Total Test Queries** | 100 | 100 | PASS |
| **Routing Accuracy** | $\ge 90.0\%$ | **96.00%** (96/100) | **PASS** |
| **Rule-Engine Match Rate** | -- | **88.0%** (88/100) | INFO |
| **LLM-Fallback Rate** | -- | **12.0%** (12/100) | INFO |
| **Average Query Latency** | $< 50$ ms | **3.31 ms** | PASS |

---

## 2. Per-Class Performance Breakdown

| Class | Ground Truth | True Positive (TP) | False Positive (FP) | False Negative (FN) | Precision | Recall |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SQL** | 40 | 38 | 1 | 2 | 97.4% | 95.0% |
| **RAG** | 40 | 40 | 3 | 0 | 93.0% | 100.0% |
| **BOTH** | 20 | 18 | 0 | 2 | 100.0% | 90.0% |

---

## 3. Sample Evaluated Queries

| ID | Expected | Predicted | Method | Latency | Status | Query |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `route-001` | `sql` | `sql` | `rule` | 0.17ms | PASS | How many purchase orders were issued in Q3 2026? |
| `route-002` | `sql` | `sql` | `rule` | 0.10ms | PASS | What is the average defect rate of hydraulic valves delivered to Hamburg? |
| `route-003` | `sql` | `sql` | `rule` | 0.08ms | PASS | Top 5 suppliers by late deliveries to Hamburg last quarter? |
| `route-004` | `sql` | `sql` | `rule` | 0.07ms | PASS | Which parts have a unit cost greater than 500 euros? |
| `route-005` | `sql` | `sql` | `default` | 317.21ms | PASS | List all active suppliers located in Germany. |
| `route-006` | `sql` | `sql` | `rule` | 0.14ms | PASS | Total spend on purchase orders in plant Stuttgart for 2026? |
| `route-007` | `sql` | `sql` | `rule` | 0.08ms | PASS | How many quality incidents were recorded for part-val-001? |
| `route-008` | `sql` | `sql` | `rule` | 0.06ms | PASS | Find all delayed shipments delivered to Munich in August. |
| `route-009` | `sql` | `sql` | `default` | 0.61ms | PASS | Count of suppliers grouped by country of origin. |
| `route-010` | `sql` | `sql` | `rule` | 0.08ms | PASS | Which 10 purchase orders had the largest total amount in 2026? |
| `route-011` | `sql` | `sql` | `rule` | 0.07ms | PASS | List suppliers with more than 3 critical severity quality incidents. |
| `route-012` | `sql` | `sql` | `rule` | 0.06ms | PASS | What is the total number of parts in category Seal? |
| `route-013` | `sql` | `sql` | `rule` | 0.22ms | PASS | Average delivery delay in days for shipments delivered to Katowice. |
| `route-014` | `sql` | `sql` | `rule` | 0.08ms | PASS | Find the cheapest supplier for hydraulic pump housing part-pmp-042. |
| `route-015` | `sql` | `sql` | `rule` | 0.06ms | PASS | How many shipments are currently marked with status delayed? |
| `route-016` | `sql` | `sql` | `rule` | 0.07ms | PASS | List purchase orders placed between 2026-01-01 and 2026-06-30. |
| `route-017` | `sql` | `sql` | `rule` | 0.06ms | PASS | Which plant received the highest number of shipments in Q2? |
| `route-018` | `sql` | `sql` | `rule` | 0.06ms | PASS | Total purchase order amount ordered by supplier supp-de-001. |
| `route-019` | `sql` | `sql` | `rule` | 0.06ms | PASS | How many active certificates are registered for supp-ch-009? |
| `route-020` | `sql` | `sql` | `rule` | 0.06ms | PASS | List all shipments with tracking numbers starting with DE-DHL. |
