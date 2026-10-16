"""Tests for Splink record linkage model configuration and persistence."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pyarrow as pa
from fieldkit_er.splink_model import (
    create_supplier_linker,
    get_supplier_splink_settings,
    save_splink_model,
)
from splink import DuckDBAPI


def test_supplier_splink_settings_structure() -> None:
    settings = get_supplier_splink_settings(link_type="dedupe_only", include_prediction_blocks=True)
    assert settings["link_type"] == "dedupe_only"
    assert len(settings["comparisons"]) == 5
    assert len(settings["blocking_rules_to_generate_predictions"]) == 4


def test_create_supplier_linker_and_predict(tmp_path: Path) -> None:
    con = duckdb.connect()
    records = [
        {
            "unique_id": 1,
            "name": "Krupp Hydraulik GmbH",
            "street": "Industriestrasse 10",
            "city": "Essen",
            "postcode": "45127",
            "country": "DE",
            "match_key": "krupphydraulik",
        },
        {
            "unique_id": 2,
            "name": "Krupp Hydraulik",
            "street": "Industriestr. 10",
            "city": "Essen",
            "postcode": "45127",
            "country": "DE",
            "match_key": "krupphydraulik",
        },
        {
            "unique_id": 3,
            "name": "Siemens AG",
            "street": "Werner-von-Siemens-Strasse 1",
            "city": "Muenchen",
            "postcode": "80333",
            "country": "DE",
            "match_key": "siemens",
        },
    ]
    tbl = pa.Table.from_pylist(records)
    con.register("suppliers", tbl)

    db_api = DuckDBAPI(connection=con)
    df = db_api.register("suppliers")

    settings = get_supplier_splink_settings(
        link_type="dedupe_only", include_prediction_blocks=False
    )
    linker = create_supplier_linker(df, db_api=db_api, settings=settings)

    # Export model to json
    out_file = tmp_path / "model.json"
    saved = save_splink_model(linker, out_file)
    assert saved.exists()

    with open(saved, encoding="utf-8") as f:
        data = json.load(f)
    assert "link_type" in data
    assert data["link_type"] == "dedupe_only"
