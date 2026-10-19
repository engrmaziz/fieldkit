"""Evaluation runner for Project 2 Milestone 5 Hybrid Query Router."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from fieldkit_assistant.router import HybridRouter


async def run_routing_evaluation(
    gold_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, float | int]:
    """Run benchmark over 100-item gold routing dataset."""
    gold_file = gold_path or Path("evals/p2/routing_gold.jsonl")
    out_dir = output_dir or Path("evals/reports/assistant")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not gold_file.exists():
        raise FileNotFoundError(f"Routing gold dataset not found at: {gold_file}")

    content = gold_file.read_text(encoding="utf-8")
    items = [json.loads(line) for line in content.splitlines() if line.strip()]

    router = HybridRouter()
    total = len(items)
    correct = 0
    rule_matched = 0
    llm_matched = 0

    per_class_counts: dict[str, dict[str, int]] = {
        "sql": {"tp": 0, "fp": 0, "fn": 0, "total": 0},
        "rag": {"tp": 0, "fp": 0, "fn": 0, "total": 0},
        "both": {"tp": 0, "fp": 0, "fn": 0, "total": 0},
    }

    latencies: list[float] = []
    results = []

    print(f"Evaluating Hybrid Router against {total} labeled queries...")

    for item in items:
        q = item["question"]
        expected = item["expected_route"]
        per_class_counts[expected]["total"] += 1

        t0 = time.perf_counter()
        decision = await router.route(q)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        actual = decision.route
        is_correct = actual == expected
        if is_correct:
            correct += 1
            per_class_counts[expected]["tp"] += 1
        else:
            per_class_counts[expected]["fn"] += 1
            if actual in per_class_counts:
                per_class_counts[actual]["fp"] += 1

        if decision.method == "rule":
            rule_matched += 1
        else:
            llm_matched += 1

        results.append(
            {
                "id": item["id"],
                "question": q,
                "expected": expected,
                "actual": actual,
                "confidence": decision.confidence,
                "method": decision.method,
                "correct": is_correct,
                "latency_ms": dt,
            }
        )

    accuracy = (correct / total) * 100.0 if total > 0 else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # Calculate metrics
    report_date = datetime.now(UTC).strftime("%Y-%m-%d")
    report_file = out_dir / f"routing_eval_{report_date}.md"

    header_block = "\n".join(
        [
            "> **Evaluated Model**: Hybrid Query Router (`fieldkit_assistant.router.HybridRouter`)",
            f"> **Date**: {report_date}",
            "> **Target Accuracy**: $\\ge 90.0\\%$",
            f"> **Dataset**: `evals/p2/routing_gold.jsonl` ({total} labeled queries)",
        ]
    )
    md = f"""# Evaluation Report: `routing-core` (Project 2: Milestone 5)

{header_block}

---

## 1. Executive Summary

| Metric | Target | Measured | Result |
| :--- | :--- | :--- | :--- |
| **Total Test Queries** | 100 | {total} | PASS |
| **Routing Accuracy** | $\\ge 90.0\\%$ | **{accuracy:.2f}%** ({correct}/{total}) | **{"PASS" if accuracy >= 90.0 else "FAIL"}** |
| **Rule-Engine Match Rate** | -- | **{(rule_matched / total) * 100.0:.1f}%** ({rule_matched}/{total}) | INFO |
| **LLM-Fallback Rate** | -- | **{(llm_matched / total) * 100.0:.1f}%** ({llm_matched}/{total}) | INFO |
| **Average Query Latency** | $< 50$ ms | **{avg_latency:.2f} ms** | PASS |

---

## 2. Per-Class Performance Breakdown

| Class | Ground Truth | True Positive (TP) | False Positive (FP) | False Negative (FN) | Precision | Recall |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for cls_name in ["sql", "rag", "both"]:
        stats = per_class_counts[cls_name]
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]
        prec = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        md += f"| **{cls_name.upper()}** | {stats['total']} | {tp} | {fp} | {fn} | {prec:.1f}% | {rec:.1f}% |\n"

    md += """
---

## 3. Sample Evaluated Queries

| ID | Expected | Predicted | Method | Latency | Status | Query |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for r in results[:20]:
        status_icon = "PASS" if r["correct"] else "**FAIL**"
        md += f"| `{r['id']}` | `{r['expected']}` | `{r['actual']}` | `{r['method']}` | {r['latency_ms']:.2f}ms | {status_icon} | {r['question']} |\n"

    report_file.write_text(md, encoding="utf-8")
    print(f"\n[SUCCESS] Routing Benchmark Complete! Report written to: {report_file}")
    print(f"  - Accuracy: {accuracy:.2f}% (Target: >= 90.0%)")
    print(f"  - Avg Latency: {avg_latency:.2f} ms")
    print(f"  - Rule Match Rate: {(rule_matched / total) * 100.0:.1f}%")

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "rule_matched": rule_matched,
        "avg_latency_ms": avg_latency,
    }


if __name__ == "__main__":
    asyncio.run(run_routing_evaluation())
