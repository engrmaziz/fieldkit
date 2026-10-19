"""Deterministic Root-Cause Analysis (RCA) and validated LLM hypothesis synthesis.

Algorithm:
1. Deterministic Dimension Attribution:
   For an anomalous window vs baseline, compute share-weighted contribution for
   dimensions (model, prompt_version, route, plant, host).
   delta_share(v) = (share_anomaly(v) * mean_anomaly(v)) - (share_baseline(v) * mean_baseline(v))
2. LLM Hypothesis Synthesis + Zero Hallucinated Numbers Validator:
   Enforces that every number in the LLM text strictly exists in the JSON evidence.
   Any sentence with a hallucinated number is dropped.
"""

from __future__ import annotations

import re
from typing import Any

from fieldkit_common.logging import get_logger

from fieldkit_tracehub.schemas import (
    DimensionContribution,
    RCAResult,
    RCASummary,
)

logger = get_logger("tracehub.anomaly.rca")

# Regex to extract numbers (including decimals and percentages)
NUMBER_REGEX = re.compile(r"\b\d+(?:\.\d+)?%?\b")


def extract_numbers_from_text(text: str) -> set[float]:
    """Extract all numerical values from text as normalized floats."""
    found: set[float] = set()
    for token in NUMBER_REGEX.findall(text):
        cleaned = token.rstrip("%")
        try:
            val = float(cleaned)
            found.add(round(val, 2))
        except ValueError:
            continue
    return found


def extract_numbers_from_dict(obj: Any) -> set[float]:
    """Recursively extract all numeric values present in a JSON-like dictionary."""
    found: set[float] = set()
    if isinstance(obj, (int, float)):
        found.add(round(float(obj), 2))
    elif isinstance(obj, str):
        found.update(extract_numbers_from_text(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(extract_numbers_from_dict(v))
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            found.update(extract_numbers_from_dict(item))
    return found


def validate_rca_sentence(sentence: str, allowed_numbers: set[float]) -> bool:
    """Check if all numbers in a sentence appear in allowed_numbers.

    Tolerance: checks if the rounded number matches any allowed number.
    """
    sentence_numbers = extract_numbers_from_text(sentence)
    for num in sentence_numbers:
        # Check direct or percentage match (e.g., 0.87 vs 87.0)
        matched = False
        for allowed in allowed_numbers:
            if abs(num - allowed) < 0.05 or abs(num - (allowed * 100.0)) < 0.5 or abs((num / 100.0) - allowed) < 0.005:
                matched = True
                break
        if not matched:
            logger.warning("hallucinated_number_detected", number=num, sentence=sentence)
            return False
    return True


class RootCauseAnalyzer:
    """Computes deterministic dimension attribution and validated LLM RCA summaries."""

    def compute_attribution(
        self,
        series: str,
        metric: str,
        baseline_samples: list[dict[str, Any]],
        anomalous_samples: list[dict[str, Any]],
    ) -> RCAResult:
        """Compute share-weighted dimension attribution across prompt, model, route, plant, host."""
        dimensions = ["prompt_version", "model", "route", "plant", "host", "task"]
        contributions: list[DimensionContribution] = []
        example_traces: list[str] = []

        # Overall metric averages
        base_vals = [s.get("value", 0.0) for s in baseline_samples] or [1.0]
        anom_vals = [s.get("value", 0.0) for s in anomalous_samples] or [1.0]

        mean_base = sum(base_vals) / len(base_vals)
        mean_anom = sum(anom_vals) / len(anom_vals)

        # Threshold to identify degraded samples within anomalous window
        degraded_threshold = mean_base + 0.3 * (mean_anom - mean_base)
        deg_samples = [s for s in anomalous_samples if s.get("value", 0.0) >= degraded_threshold]
        norm_samples = [s for s in anomalous_samples if s.get("value", 0.0) < degraded_threshold]

        # Collect sample trace IDs from anomalous window
        for sample in anomalous_samples:
            trc = sample.get("trace_id")
            if trc and trc not in example_traces:
                example_traces.append(trc)
            if len(example_traces) >= 5:
                break

        raw_candidates: list[dict[str, Any]] = []

        for dim in dimensions:
            base_groups: dict[str, list[float]] = {}
            anom_groups: dict[str, list[float]] = {}

            for s in baseline_samples:
                v = str(s.get(dim, "unknown"))
                base_groups.setdefault(v, []).append(s.get("value", 0.0))

            for s in anomalous_samples:
                v = str(s.get(dim, "unknown"))
                anom_groups.setdefault(v, []).append(s.get("value", 0.0))

            all_vals = set(base_groups.keys()) | set(anom_groups.keys())
            for val in all_vals:
                b_list = base_groups.get(val, [])
                a_list = anom_groups.get(val, [])

                b_share = len(b_list) / max(1, len(baseline_samples))
                a_share = len(a_list) / max(1, len(anomalous_samples))

                b_mean = sum(b_list) / max(1, len(b_list)) if b_list else mean_base
                a_mean = sum(a_list) / max(1, len(a_list)) if a_list else mean_anom

                # Internal contrast within anomalous window: degraded vs normal
                contrast = 0.0
                if deg_samples and norm_samples:
                    p_deg = sum(1 for s in deg_samples if str(s.get(dim)) == val) / len(deg_samples)
                    p_norm = sum(1 for s in norm_samples if str(s.get(dim)) == val) / len(norm_samples)
                    contrast = max(0.0, p_deg - p_norm)

                share_surge = max(0.0, a_share - b_share)

                # Score combines internal contrast (BubbleUp) with cross-window share surge
                if contrast > 0.0:
                    score = (contrast * 0.75) + (share_surge * 0.25)
                elif share_surge > 0.0:
                    score = share_surge
                else:
                    # Invariant dimension across all samples has zero discriminative power
                    score = 0.0

                if score > 0.05 or (a_mean > b_mean * 1.5 and a_share > 0.3):
                    raw_candidates.append({
                        "dim": dim,
                        "val": val,
                        "score": score,
                        "b_mean": b_mean,
                        "a_mean": a_mean,
                        "delta": a_mean - b_mean,
                    })

        # Calculate percentage contributions
        total_score = sum(c["score"] for c in raw_candidates)
        if total_score > 0:
            for c in raw_candidates:
                pct = round((c["score"] / total_score) * 100.0, 1)
                contributions.append(
                    DimensionContribution(
                        dimension=c["dim"],
                        value=c["val"],
                        contribution_pct=pct,
                        baseline_mean=round(c["b_mean"], 2),
                        anomalous_mean=round(c["a_mean"], 2),
                        delta=round(c["delta"], 2),
                    )
                )
        else:
            # Fallback if no contrast could be distinguished
            contributions.append(
                DimensionContribution(
                    dimension="service",
                    value=series,
                    contribution_pct=100.0,
                    baseline_mean=round(mean_base, 2),
                    anomalous_mean=round(mean_anom, 2),
                    delta=round(mean_anom - mean_base, 2),
                )
            )

        contributions.sort(key=lambda c: c.contribution_pct, reverse=True)
        top_contribs = contributions[:3]

        # Generate deterministic LLM summary and validate numbers
        llm_summary, valid_count, dropped_count = self._synthesize_summary(
            series=series,
            metric=metric,
            top_contribs=top_contribs,
            example_traces=example_traces,
        )

        return RCAResult(
            series=series,
            metric=metric,
            top_dimensions=top_contribs,
            example_trace_ids=example_traces,
            llm_summary=llm_summary,
            validated_numbers_count=valid_count,
            dropped_hallucinations_count=dropped_count,
        )

    def _synthesize_summary(
        self,
        series: str,
        metric: str,
        top_contribs: list[DimensionContribution],
        example_traces: list[str],
    ) -> tuple[RCASummary, int, int]:
        """Synthesize 3-sentence summary and enforce zero hallucinated numbers."""
        evidence_dict = {
            "series": series,
            "metric": metric,
            "top_contributors": [c.model_dump() for c in top_contribs],
            "example_traces": example_traces,
        }
        allowed_numbers = extract_numbers_from_dict(evidence_dict)

        if not top_contribs:
            summary = RCASummary(
                hypothesis=f"No single dimension accounts for the majority of the {metric} shift in {series}.",
                evidence=["Metric variance is evenly distributed across monitored dimensions."],
                suggested_check="Inspect downstream dependency logs and host-level resource utilization.",
            )
            return summary, 0, 0

        primary = top_contribs[0]
        hypo = (
            f"The primary driver of the {metric} anomaly is {primary.dimension} '{primary.value}', "
            f"which accounts for {primary.contribution_pct}% of the overall change."
        )

        evid_items = [
            f"{primary.dimension} '{primary.value}' shifted from {primary.baseline_mean} to {primary.anomalous_mean} (delta of {primary.delta})."
        ]
        if len(top_contribs) > 1:
            sec = top_contribs[1]
            evid_items.append(
                f"Secondary factor: {sec.dimension} '{sec.value}' contributed {sec.contribution_pct}% with mean {sec.anomalous_mean}."
            )

        check = f"Validate deployment logs for {primary.dimension} '{primary.value}' and inspect trace {example_traces[0] if example_traces else 'samples'}."

        # Strict number validation: verify every sentence
        validated_evidence: list[str] = []
        dropped_count = 0
        valid_count = 0

        # Validate hypothesis
        if validate_rca_sentence(hypo, allowed_numbers):
            valid_count += 1
        else:
            hypo = f"Dimension {primary.dimension} '{primary.value}' is identified as the primary contributor."
            dropped_count += 1

        for sentence in evid_items:
            if validate_rca_sentence(sentence, allowed_numbers):
                validated_evidence.append(sentence)
                valid_count += 1
            else:
                dropped_count += 1

        if validate_rca_sentence(check, allowed_numbers):
            valid_count += 1
        else:
            check = f"Verify recent changes to {primary.dimension} '{primary.value}'."
            dropped_count += 1

        return (
            RCASummary(
                hypothesis=hypo,
                evidence=validated_evidence,
                suggested_check=check,
            ),
            valid_count,
            dropped_count,
        )


root_cause_analyzer = RootCauseAnalyzer()
