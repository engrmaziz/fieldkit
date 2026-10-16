"""Splink 4/5 Probabilistic Record Linkage Model for Enterprise Suppliers.

Configures:
- Blocking rules on postcode + match_key substring and city + match_key
- Multi-level comparisons on name (Jaro-Winkler 0.95, 0.88, 0.70), street, postcode, city, and country
- Fellegi-Sunter parameter estimation (m and u)
- Clustering into canonical supplier clusters
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import splink.blocking_rule_library as brl
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker


def get_supplier_splink_settings(
    link_type: str = "dedupe_only",
    include_prediction_blocks: bool = True,
) -> dict[str, Any]:
    """Returns Splink configuration dictionary for supplier entity resolution."""
    comparisons = [
        cl.JaroWinklerAtThresholds("name", [0.95, 0.88, 0.70]),
        cl.ExactMatch("street"),
        cl.ExactMatch("city"),
        cl.ExactMatch("postcode"),
        cl.ExactMatch("country"),
    ]

    blocking_rules: list[Any] = []
    if include_prediction_blocks:
        blocking_rules = [
            brl.CustomRule(
                "l.postcode = r.postcode and substr(l.match_key, 1, 3) = substr(r.match_key, 1, 3)"
            ),
            brl.CustomRule(
                "l.city = r.city and substr(l.match_key, 1, 3) = substr(r.match_key, 1, 3)"
            ),
            brl.block_on("postcode"),
            brl.block_on("city"),
        ]

    return {
        "link_type": link_type,
        "comparisons": comparisons,
        "blocking_rules_to_generate_predictions": blocking_rules,
        "probability_two_random_records_match": 0.0001,
    }


def create_supplier_linker(
    tables: Any,
    db_api: DuckDBAPI | None = None,
    settings: dict[str, Any] | None = None,
) -> Linker:
    """Initializes and returns a Splink Linker configured for supplier entity resolution."""
    cfg = settings or get_supplier_splink_settings()
    return Linker(tables, cfg)


def save_splink_model(
    linker: Linker,
    output_path: str | Path = "models/er/splink_model.json",
) -> Path:
    """Exports trained Splink model parameters to disk."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    linker.misc.save_model_to_json(str(out), overwrite=True)
    return out
