# Project 6: Cost-Optimized Decision Engine Report (Milestone 3)

> **Date**: 2026-10-21\
> **Customer**: Halden Industrie GmbH (Plant Safety & Quality Operations, Hamburg `DE-HAM`)\
> **Persona**: Mehmet Yilmaz (Quality Lead)\
> **Asymmetric Costs**: False Pass = 500 €, False Reject = 25 €, Operator Review = 5 €\
> **Review Queue Budget**: $\le 8.0\%$\
> **Overall Gate Status**: **PASSED (All Targets Met)**

---

## 1. Executive Summary & Quality Gates

| Evaluation Metric | Target Threshold | Measured Result | Status |
| :--- | :--- | :--- | :---: |
| **Defect Escape Rate (False Pass)** | **Strictly 0.0%** | **0.00%** (0 escapes / 100) | PASS |
| **Operator Review Rate** | $\le 8.0\%$ | **7.00%** (7 routed to review) | PASS |
| **Cost Reduction vs. Naive Cutoff** | $\ge 3.0\times$ | **57.1x reduction** (35.00 € vs 2000.00 €) | PASS |
| **2% Random Seeded Audit Sampling** | $2.0\% \pm 1.0\%$ | **1 audit samples** (1.0%) | PASS |
| **End-to-End Decision Latency (P95)**| $< 100.0\text{ ms}$ | **22.3 ms** | PASS |

---

## 2. Shop-Floor Component Disposition Breakdown (100 Tested Parts)

- **Total Inspected Parts**: 100
- **True Passes (Shipped Clean)**: 69
- **True Rejects (Scrapped / Reworked)**: 24
- **Ambiguous Routed to Review Queue**: 7
  * Borderline anomaly scores in $[T_{pass}, T_{reject}]$
  * Low-confidence defect predictions
  * Homography alignment faults
- **False Rejects (Over-scrap)**: 0
- **Escapes to Customer**: **0 (Zero defect escapes)**

---

## 3. Asymmetric Cost Analysis & Financial Impact
- **Total Manufacturing Cost Under Decision Engine**: **35.00 €** (0.35 €/part)
- **Baseline Naive Single-Threshold Cutoff Cost**: **2000.00 €**
- **Net Cost Savings**: **1965.00 € per 100 parts (57.1x cost efficiency)**
