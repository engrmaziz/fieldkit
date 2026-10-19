"""Evaluation benchmark run storage and statistical regression comparison engine."""

from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime

from fieldkit_common.logging import get_logger

from fieldkit_tracehub.schemas import (
    EvalComparisonResponse,
    EvalItem,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunSummary,
    ItemRegression,
    MetricDeltaWithCI,
)

logger = get_logger("tracehub.evals")


class EvalEngine:
    """Manages benchmark evaluation runs and item-level regression comparisons."""

    def __init__(self) -> None:
        self._runs: dict[str, EvalRunDetail] = {}
        self._seed_default_eval_runs()

    def store_eval_run(self, create: EvalRunCreate) -> EvalRunDetail:
        """Store an evaluation benchmark run."""
        run_id = create.run_id or f"run-{uuid.uuid4().hex[:10]}"
        detail = EvalRunDetail(
            run_id=run_id,
            suite=create.suite,
            model=create.model,
            prompt_versions=create.prompt_versions,
            git_sha=create.git_sha or "HEAD",
            total_items=len(create.items),
            aggregates=create.aggregates,
            timestamp=datetime.now(UTC),
            items=create.items,
        )
        self._runs[run_id] = detail
        logger.info(
            "eval_run_stored",
            run_id=run_id,
            suite=create.suite,
            model=create.model,
            items_count=len(create.items),
        )
        return detail

    def list_eval_runs(self, suite: str | None = None) -> list[EvalRunSummary]:
        """List summary records for all stored evaluation benchmark runs."""
        summaries: list[EvalRunSummary] = []
        for r in self._runs.values():
            if suite and r.suite != suite:
                continue
            summaries.append(
                EvalRunSummary(
                    run_id=r.run_id,
                    suite=r.suite,
                    model=r.model,
                    prompt_versions=r.prompt_versions,
                    git_sha=r.git_sha,
                    total_items=r.total_items,
                    aggregates=r.aggregates,
                    timestamp=r.timestamp,
                )
            )
        summaries.sort(key=lambda s: s.timestamp, reverse=True)
        return summaries

    def get_eval_run(self, run_id: str) -> EvalRunDetail | None:
        """Retrieve full details of a single evaluation run."""
        return self._runs.get(run_id)

    def compare_eval_runs(
        self,
        baseline_id: str,
        candidate_id: str,
        n_bootstraps: int = 1000,
    ) -> EvalComparisonResponse | None:
        """Compare candidate run vs baseline run item-by-item with 95% bootstrap CI."""
        base = self.get_eval_run(baseline_id)
        cand = self.get_eval_run(candidate_id)
        if not base or not cand:
            return None

        # Index items by ID
        base_items = {item.id: item for item in base.items}
        cand_items = {item.id: item for item in cand.items}
        common_ids = set(base_items.keys()) & set(cand_items.keys())

        # Determine all metrics evaluated
        metrics: set[str] = set()
        for it in base.items:
            metrics.update(it.scores.keys())
        for it in cand.items:
            metrics.update(it.scores.keys())
        if not metrics:
            metrics = set(base.aggregates.keys()) | set(cand.aggregates.keys())

        metric_deltas: dict[str, MetricDeltaWithCI] = {}
        regressions: list[ItemRegression] = []
        improvements: list[ItemRegression] = []
        unchanged_count = 0

        for metric in sorted(metrics):
            paired_deltas: list[float] = []
            base_scores: list[float] = []
            cand_scores: list[float] = []

            for item_id in common_ids:
                b_val = base_items[item_id].scores.get(metric)
                c_val = cand_items[item_id].scores.get(metric)

                if b_val is not None and c_val is not None:
                    d = round(c_val - b_val, 4)
                    paired_deltas.append(d)
                    base_scores.append(b_val)
                    cand_scores.append(c_val)

                    q_text = cand_items[item_id].question or base_items[item_id].question
                    trc_id = cand_items[item_id].trace_id or base_items[item_id].trace_id

                    if d < -0.001:
                        regressions.append(
                            ItemRegression(
                                item_id=item_id,
                                question=q_text,
                                metric=metric,
                                baseline_score=b_val,
                                candidate_score=c_val,
                                delta=d,
                                trace_id=trc_id,
                            )
                        )
                    elif d > 0.001:
                        improvements.append(
                            ItemRegression(
                                item_id=item_id,
                                question=q_text,
                                metric=metric,
                                baseline_score=b_val,
                                candidate_score=c_val,
                                delta=d,
                                trace_id=trc_id,
                            )
                        )
                    else:
                        unchanged_count += 1

            # Aggregate scores
            b_agg = base.aggregates.get(metric, sum(base_scores) / max(1, len(base_scores)))
            c_agg = cand.aggregates.get(metric, sum(cand_scores) / max(1, len(cand_scores)))
            delta_val = round(c_agg - b_agg, 4)

            # Bootstrap 95% Confidence Interval computation
            if paired_deltas:
                ci_low, ci_high = self._compute_bootstrap_ci(paired_deltas, n_bootstraps=n_bootstraps)
                # Significant if 0 is strictly outside confidence interval
                is_significant = (ci_low > 0) or (ci_high < 0)
            else:
                ci_low, ci_high = delta_val, delta_val
                is_significant = False

            metric_deltas[metric] = MetricDeltaWithCI(
                metric=metric,
                baseline_score=round(b_agg, 4),
                candidate_score=round(c_agg, 4),
                delta=delta_val,
                ci_lower=round(ci_low, 4),
                ci_upper=round(ci_high, 4),
                significant=is_significant,
            )

        regressions.sort(key=lambda r: r.delta)
        improvements.sort(key=lambda r: r.delta, reverse=True)

        return EvalComparisonResponse(
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            suite=cand.suite or base.suite,
            metric_deltas=metric_deltas,
            regressions=regressions,
            improvements=improvements,
            total_items_compared=len(common_ids),
            total_regressions=len(regressions),
            total_improvements=len(improvements),
            total_unchanged=unchanged_count,
        )

    def _compute_bootstrap_ci(
        self,
        deltas: list[float],
        n_bootstraps: int = 1000,
        alpha: float = 0.05,
    ) -> tuple[float, float]:
        """Compute empirical percentile bootstrap 95% confidence interval."""
        n = len(deltas)
        if n < 5:
            # For small samples, use mean delta with conservative bounds
            mean_val = sum(deltas) / max(1, n)
            return (mean_val - 0.02, mean_val + 0.02)

        rng = random.Random(42)  # Deterministic seed for reproducible CI
        boot_means: list[float] = []
        for _ in range(n_bootstraps):
            sample = [rng.choice(deltas) for _ in range(n)]
            boot_means.append(sum(sample) / n)

        boot_means.sort()
        low_idx = int(math.floor(n_bootstraps * (alpha / 2.0)))
        high_idx = int(math.ceil(n_bootstraps * (1.0 - alpha / 2.0))) - 1

        ci_low = boot_means[max(0, min(low_idx, n_bootstraps - 1))]
        ci_high = boot_means[max(0, min(high_idx, n_bootstraps - 1))]
        return (ci_low, ci_high)

    def _seed_default_eval_runs(self) -> None:
        """Pre-populate baseline and candidate evaluation runs for console demo."""
        # Baseline run: v1.0.0
        v1_items = [
            EvalItem(
                id="q-001",
                question="What is the surface roughness tolerance for hydraulic cylinders in Plant Hamburg?",
                scores={"faithfulness": 0.95, "citation_accuracy": 1.0},
                output="Plant Hamburg honing operations mandate a maximum surface roughness Ra of 0.4 µm [1].",
                trace_id="trc-8a1f2b904c12",
                passed=True,
            ),
            EvalItem(
                id="q-002",
                question="What does DIN EN ISO 4413 specify for hydraulic safety shut-off valves?",
                scores={"faithfulness": 0.90, "citation_accuracy": 1.0},
                output="DIN EN ISO 4413 mandates redundant pressure relief valves [2].",
                trace_id="trc-7e3d1a802f55",
                passed=True,
            ),
            EvalItem(
                id="q-003",
                question="What are the confidential supplier audit penalties?",
                scores={"faithfulness": 0.85, "citation_accuracy": 0.8},
                output="Suppliers failing audit incur contract penalty clauses [3].",
                trace_id="trc-9c4e2a101f33",
                passed=True,
            ),
            EvalItem(
                id="q-004",
                question="Explain emergency stop protocol for CNC lathe spindles.",
                scores={"faithfulness": 0.80, "citation_accuracy": 0.7},
                output="Press emergency button to cut main circuit immediately [4].",
                trace_id="trc-1b2c3d4e5f60",
                passed=False,
            ),
        ]
        self.store_eval_run(
            EvalRunCreate(
                run_id="run-p2-v1-baseline",
                suite="assistant_rag",
                model="qwen2.5:7b",
                prompt_versions={"rag_answer": "1.0.0"},
                git_sha="1e0fd9b",
                items=v1_items,
                aggregates={"faithfulness": 0.875, "citation_accuracy": 0.875},
            )
        )

        # Candidate run: v2.0.0 (q-004 improved to 0.95, q-003 slight regression to 0.70)
        v2_items = [
            EvalItem(
                id="q-001",
                question="What is the surface roughness tolerance for hydraulic cylinders in Plant Hamburg?",
                scores={"faithfulness": 0.95, "citation_accuracy": 1.0},
                output="Plant Hamburg honing operations mandate a maximum surface roughness Ra of 0.4 µm [1].",
                trace_id="trc-8a1f2b904c12",
                passed=True,
            ),
            EvalItem(
                id="q-002",
                question="What does DIN EN ISO 4413 specify for hydraulic safety shut-off valves?",
                scores={"faithfulness": 0.95, "citation_accuracy": 1.0},
                output="DIN EN ISO 4413 mandates redundant pressure relief valves [2].",
                trace_id="trc-7e3d1a802f55",
                passed=True,
            ),
            EvalItem(
                id="q-003",
                question="What are the confidential supplier audit penalties?",
                scores={"faithfulness": 0.70, "citation_accuracy": 0.7},
                output="Audit details not fully cited [3].",
                trace_id="trc-9c4e2a101f33",
                passed=False,
            ),
            EvalItem(
                id="q-004",
                question="Explain emergency stop protocol for CNC lathe spindles.",
                scores={"faithfulness": 0.95, "citation_accuracy": 1.0},
                output="Press emergency button cutting spindle drive power within 150ms per SOP-SAF-002 [4].",
                trace_id="trc-1b2c3d4e5f60",
                passed=True,
            ),
        ]
        self.store_eval_run(
            EvalRunCreate(
                run_id="run-p2-v2-candidate",
                suite="assistant_rag",
                model="qwen2.5:7b",
                prompt_versions={"rag_answer": "2.0.0"},
                git_sha="e16320f",
                items=v2_items,
                aggregates={"faithfulness": 0.8875, "citation_accuracy": 0.925},
            )
        )


eval_engine = EvalEngine()
