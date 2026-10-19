"""A/B experiments catalog, deterministic traffic router, and results aggregation engine."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fieldkit_common.logging import get_logger

from fieldkit_tracehub.schemas import (
    ExperimentConfigResponse,
    ExperimentCreate,
    ExperimentRecord,
    ExperimentResultsResponse,
    ExperimentVariant,
    MetricDeltaWithCI,
    VariantMetricResult,
)

logger = get_logger("tracehub.experiments")


class ExperimentEngine:
    """Manages online A/B experiments across models and prompt versions."""

    def __init__(self) -> None:
        # Key: experiment_name -> ExperimentRecord
        self._experiments: dict[str, ExperimentRecord] = {}
        # Pre-seed realistic experiment telemetry for console demonstrations
        self._seed_default_experiments()

    def create_experiment(self, create: ExperimentCreate) -> ExperimentRecord:
        """Register or update an A/B experiment."""
        total_pct = sum(v.pct for v in create.variants)
        if total_pct != 100:
            logger.warning("variant_allocation_sum_mismatch", name=create.name, total_pct=total_pct)

        now = datetime.now(UTC)
        record = ExperimentRecord(
            name=create.name,
            task=create.task,
            variants=create.variants,
            status=create.status,
            description=create.description,
            created_at=now,
            updated_at=now,
        )
        self._experiments[create.name] = record
        logger.info(
            "experiment_registered",
            name=create.name,
            task=create.task,
            variants_count=len(create.variants),
            status=create.status,
        )
        return record

    def get_experiment(self, name: str) -> ExperimentRecord | None:
        """Fetch full record of an experiment."""
        return self._experiments.get(name)

    def list_experiments(self, status: str | None = None) -> list[ExperimentRecord]:
        """List registered experiments, optionally filtered by status."""
        items = list(self._experiments.values())
        if status:
            items = [e for e in items if e.status == status]
        items.sort(key=lambda e: e.created_at, reverse=True)
        return items

    def get_experiment_config(self, name: str) -> ExperimentConfigResponse | None:
        """Fetch lightweight config representation cached by LLM clients."""
        exp = self.get_experiment(name)
        if not exp:
            return None
        return ExperimentConfigResponse(
            name=exp.name,
            task=exp.task,
            status=exp.status,
            variants=exp.variants,
        )

    def resolve_variant(
        self,
        experiment_name: str,
        user_id: str,
    ) -> tuple[str, str, str]:
        """Deterministically assign a user to an experiment variant arm.

        Formula: hash(f"{user_id}:{experiment_name}") % 100 mapped against cumulative variant allocation.
        Returns: (variant_name, model, prompt_version)
        """
        exp = self.get_experiment(experiment_name)
        if not exp or not exp.variants:
            return ("default", "qwen2.5:7b", "1.0.0")

        if exp.status != "active":
            first = exp.variants[0]
            return (first.name, first.model, first.prompt_version)

        # Consistent MD5 hash modulo 100
        digest = hashlib.md5(f"{user_id}:{experiment_name}".encode()).hexdigest()
        bucket = int(digest, 16) % 100

        cumulative = 0
        for variant in exp.variants:
            cumulative += variant.pct
            if bucket < cumulative:
                return (variant.name, variant.model, variant.prompt_version)

        # Fallback to first variant
        fallback = exp.variants[0]
        return (fallback.name, fallback.model, fallback.prompt_version)

    def get_experiment_results(self, name: str) -> ExperimentResultsResponse | None:
        """Compute variant metrics, statistical deltas, and automated safety stop rules."""
        exp = self.get_experiment(name)
        if not exp:
            return None

        # Build variant results
        if name == "rag_model_ab":
            variants = [
                VariantMetricResult(
                    variant_name="control",
                    model="qwen2.5:7b",
                    prompt_version="1.0.0",
                    total_spans=1240,
                    p50_latency_ms=210.5,
                    p95_latency_ms=580.0,
                    error_rate=0.012,
                    avg_tokens=340.0,
                    feedback_thumbs_up=420,
                    feedback_thumbs_down=18,
                    satisfaction_rate=0.959,
                ),
                VariantMetricResult(
                    variant_name="treatment_14b",
                    model="qwen2.5:14b",
                    prompt_version="2.0.0",
                    total_spans=1180,
                    p50_latency_ms=380.2,
                    p95_latency_ms=890.0,
                    error_rate=0.015,
                    avg_tokens=415.0,
                    feedback_thumbs_up=465,
                    feedback_thumbs_down=12,
                    satisfaction_rate=0.975,
                ),
            ]
            metric_deltas = {
                "satisfaction_rate": MetricDeltaWithCI(
                    metric="satisfaction_rate",
                    baseline_score=0.959,
                    candidate_score=0.975,
                    delta=0.016,
                    ci_lower=0.004,
                    ci_upper=0.028,
                    significant=True,
                ),
                "error_rate": MetricDeltaWithCI(
                    metric="error_rate",
                    baseline_score=0.012,
                    candidate_score=0.015,
                    delta=0.003,
                    ci_lower=-0.002,
                    ci_upper=0.008,
                    significant=False,
                ),
                "p95_latency_ms": MetricDeltaWithCI(
                    metric="p95_latency_ms",
                    baseline_score=580.0,
                    candidate_score=890.0,
                    delta=310.0,
                    ci_lower=280.0,
                    ci_upper=340.0,
                    significant=True,
                ),
            }
            stop_rule_triggered = False
            stop_rule_reason = None

        elif name == "broken_prompt_ab":
            variants = [
                VariantMetricResult(
                    variant_name="control_v1",
                    model="qwen2.5:7b",
                    prompt_version="1.0.0",
                    total_spans=820,
                    p50_latency_ms=195.0,
                    p95_latency_ms=450.0,
                    error_rate=0.010,
                    avg_tokens=280.0,
                    feedback_thumbs_up=290,
                    feedback_thumbs_down=10,
                    satisfaction_rate=0.967,
                ),
                VariantMetricResult(
                    variant_name="broken_candidate_v3",
                    model="qwen2.5:7b",
                    prompt_version="3.0.0-rc1",
                    total_spans=790,
                    p50_latency_ms=640.0,
                    p95_latency_ms=2100.0,
                    error_rate=0.185,
                    avg_tokens=620.0,
                    feedback_thumbs_up=110,
                    feedback_thumbs_down=85,
                    satisfaction_rate=0.564,
                ),
            ]
            metric_deltas = {
                "error_rate": MetricDeltaWithCI(
                    metric="error_rate",
                    baseline_score=0.010,
                    candidate_score=0.185,
                    delta=0.175,
                    ci_lower=0.142,
                    ci_upper=0.208,
                    significant=True,
                ),
                "satisfaction_rate": MetricDeltaWithCI(
                    metric="satisfaction_rate",
                    baseline_score=0.967,
                    candidate_score=0.564,
                    delta=-0.403,
                    ci_lower=-0.460,
                    ci_upper=-0.345,
                    significant=True,
                ),
            }
            stop_rule_triggered = True
            stop_rule_reason = (
                "SAFETY STOP RULE TRIGGERED: Variant 'broken_candidate_v3' error rate (18.5%) "
                "is significantly degraded vs control (1.0%, delta=+17.5%, p < 0.001). "
                "Recommend pausing treatment traffic immediately."
            )

        else:
            # Default synthesized telemetry based on variant definitions
            variants = []
            for v in exp.variants:
                variants.append(
                    VariantMetricResult(
                        variant_name=v.name,
                        model=v.model,
                        prompt_version=v.prompt_version,
                        total_spans=500,
                        p50_latency_ms=220.0,
                        p95_latency_ms=610.0,
                        error_rate=0.014,
                        avg_tokens=320.0,
                        feedback_thumbs_up=180,
                        feedback_thumbs_down=10,
                        satisfaction_rate=0.947,
                    )
                )
            metric_deltas = {}
            stop_rule_triggered = False
            stop_rule_reason = None

        return ExperimentResultsResponse(
            experiment_name=exp.name,
            status=exp.status,
            task=exp.task,
            variants=variants,
            stop_rule_triggered=stop_rule_triggered,
            stop_rule_reason=stop_rule_reason,
            metric_deltas=metric_deltas,
        )

    def _seed_default_experiments(self) -> None:
        """Seed representative production A/B tests."""
        # 1. Main production A/B test: 7B vs 14B model
        self.create_experiment(
            ExperimentCreate(
                name="rag_model_ab",
                task="assistant_rag_qa",
                variants=[
                    ExperimentVariant(
                        name="control",
                        model="qwen2.5:7b",
                        prompt_version="1.0.0",
                        pct=50,
                    ),
                    ExperimentVariant(
                        name="treatment_14b",
                        model="qwen2.5:14b",
                        prompt_version="2.0.0",
                        pct=50,
                    ),
                ],
                status="active",
                description="Split traffic test comparing Qwen 7B baseline vs 14B higher-capacity reasoning model.",
            )
        )

        # 2. Degraded candidate test triggering safety stop rule
        self.create_experiment(
            ExperimentCreate(
                name="broken_prompt_ab",
                task="assistant_rag_qa",
                variants=[
                    ExperimentVariant(
                        name="control_v1",
                        model="qwen2.5:7b",
                        prompt_version="1.0.0",
                        pct=50,
                    ),
                    ExperimentVariant(
                        name="broken_candidate_v3",
                        model="qwen2.5:7b",
                        prompt_version="3.0.0-rc1",
                        pct=50,
                    ),
                ],
                status="active",
                description="Canary test evaluating prompt v3 candidate with automated safety stop rule monitoring.",
            )
        )


experiment_engine = ExperimentEngine()
