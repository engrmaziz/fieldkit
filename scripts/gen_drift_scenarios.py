"""Generates 20 deterministic schema drift evaluation scenarios for Project 1."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def create_scenarios(base_dir: Path | str = "evals/p1/drift_scenarios") -> None:
    out_dir = Path(base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Base records for erp_vendors
    erp_base = [
        {
            "vendor_id": f"V{i:04d}",
            "company_name": f"Vendor {i} GmbH",
            "street": f"Hauptstrasse {i}",
            "city": "Hamburg",
            "postal_code": "20095",
            "country": "DE",
            "payment_terms": "30_DAYS",
            "currency": "EUR",
        }
        for i in range(1, 51)
    ]

    # 2. Base records for purchase_orders
    po_base = [
        {
            "po_number": f"PO-{i:05d}",
            "vendor_id": f"V{i:04d}",
            "part_number": f"PART-{i % 10}",
            "quantity": 50,
            "unit_price": 45.50,
            "order_date": "2025-01-15",
            "status": "APPROVED",
        }
        for i in range(1, 51)
    ]

    # 3. Base records for quality_incidents
    inc_base = [
        {
            "incident_id": f"INC-{i:05d}",
            "po_number": f"PO-{i:05d}",
            "defect_type": "BURR",
            "severity": "HIGH",
            "notes_de": f"Fehler {i}",
            "notes_en": f"Defect {i}",
        }
        for i in range(1, 51)
    ]

    # 4. Base records for soap_certs
    soap_base = [
        {
            "soap_vendor_id": f"SV-{i:04d}",
            "company_name": f"Supplier {i}",
            "status": "ACTIVE",
            "certificate_id": f"CERT-{i}",
            "issued_date": "2024-01-01",
            "expiry_date": "2026-01-01",
        }
        for i in range(1, 51)
    ]

    scenarios = [
        # Scenarios 1-6: Dropped contract required columns (BLOCK)
        {
            "id": "scenario_01_drop_vendor_id",
            "name": "Drop required vendor_id column in erp_vendors",
            "contract": "erp_vendors.yaml",
            "source": "erp_vendors",
            "records": [{k: v for k, v in r.items() if k != "vendor_id"} for r in erp_base],
            "baseline": erp_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "vendor_id"}
            ],
        },
        {
            "id": "scenario_02_drop_po_number",
            "name": "Drop required po_number in purchase_orders",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{k: v for k, v in r.items() if k != "po_number"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "po_number"}
            ],
        },
        {
            "id": "scenario_03_drop_incident_id",
            "name": "Drop required incident_id in quality_incidents",
            "contract": "quality_incidents.yaml",
            "source": "quality_incidents",
            "records": [{k: v for k, v in r.items() if k != "incident_id"} for r in inc_base],
            "baseline": inc_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "incident_id"}
            ],
        },
        {
            "id": "scenario_04_drop_order_date",
            "name": "Drop required order_date in purchase_orders",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{k: v for k, v in r.items() if k != "order_date"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "order_date"}
            ],
        },
        {
            "id": "scenario_05_drop_unit_price",
            "name": "Drop required unit_price in purchase_orders",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{k: v for k, v in r.items() if k != "unit_price"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "unit_price"}
            ],
        },
        {
            "id": "scenario_06_drop_soap_vendor_id",
            "name": "Drop required soap_vendor_id in soap_certs",
            "contract": "soap_certs.yaml",
            "source": "soap_certs",
            "records": [{k: v for k, v in r.items() if k != "soap_vendor_id"} for r in soap_base],
            "baseline": soap_base,
            "expected_events": [
                {
                    "event_type": "COLUMN_REMOVED",
                    "severity": "BLOCK",
                    "column_name": "soap_vendor_id",
                }
            ],
        },
        # Scenarios 7-10: Renamed columns (BLOCK / WARN with LLM rename suggestion)
        {
            "id": "scenario_07_rename_company_name",
            "name": "Rename company_name to firm_name in erp_vendors",
            "contract": "erp_vendors.yaml",
            "source": "erp_vendors",
            "records": [
                {("firm_name" if k == "company_name" else k): v for k, v in r.items()}
                for r in erp_base
            ],
            "baseline": erp_base,
            "expected_events": [
                {
                    "event_type": "COLUMN_REMOVED",
                    "severity": "BLOCK",
                    "column_name": "company_name",
                },
                {"event_type": "COLUMN_ADDED", "severity": "WARN", "column_name": "firm_name"},
            ],
            "expected_mapping": {"old_name": "company_name", "new_name": "firm_name"},
        },
        {
            "id": "scenario_08_rename_order_date",
            "name": "Rename order_date to bestelldatum in purchase_orders",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [
                {("bestelldatum" if k == "order_date" else k): v for k, v in r.items()}
                for r in po_base
            ],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "order_date"},
                {"event_type": "COLUMN_ADDED", "severity": "WARN", "column_name": "bestelldatum"},
            ],
            "expected_mapping": {"old_name": "order_date", "new_name": "bestelldatum"},
        },
        {
            "id": "scenario_09_rename_unit_price",
            "name": "Rename unit_price to einzelpreis in purchase_orders",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [
                {("einzelpreis" if k == "unit_price" else k): v for k, v in r.items()}
                for r in po_base
            ],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "BLOCK", "column_name": "unit_price"},
                {"event_type": "COLUMN_ADDED", "severity": "WARN", "column_name": "einzelpreis"},
            ],
            "expected_mapping": {"old_name": "unit_price", "new_name": "einzelpreis"},
        },
        {
            "id": "scenario_10_rename_street",
            "name": "Rename optional street to adresse_strasse in erp_vendors",
            "contract": "erp_vendors.yaml",
            "source": "erp_vendors",
            "records": [
                {("adresse_strasse" if k == "street" else k): v for k, v in r.items()}
                for r in erp_base
            ],
            "baseline": erp_base,
            "expected_events": [
                {"event_type": "COLUMN_REMOVED", "severity": "WARN", "column_name": "street"},
                {
                    "event_type": "COLUMN_ADDED",
                    "severity": "WARN",
                    "column_name": "adresse_strasse",
                },
            ],
            "expected_mapping": {"old_name": "street", "new_name": "adresse_strasse"},
        },
        # Scenarios 11-14: Dtype changes / corruptions (BLOCK)
        {
            "id": "scenario_11_dtype_corrupt_unit_price",
            "name": "Corrupt unit_price with non-numeric string values",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "unit_price": "UNPRICED"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "DTYPE_CHANGED", "severity": "BLOCK", "column_name": "unit_price"}
            ],
        },
        {
            "id": "scenario_12_dtype_corrupt_quantity",
            "name": "Corrupt quantity integer with string words",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "quantity": "FIFTY_PIECES"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "DTYPE_CHANGED", "severity": "BLOCK", "column_name": "quantity"}
            ],
        },
        {
            "id": "scenario_13_dtype_corrupt_unit_price_symbols",
            "name": "Corrupt unit_price with non-parseable symbols",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "unit_price": "###"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "DTYPE_CHANGED", "severity": "BLOCK", "column_name": "unit_price"}
            ],
        },
        {
            "id": "scenario_14_dtype_corrupt_quantity_unknown",
            "name": "Corrupt quantity with UNKNOWN strings",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "quantity": "UNKNOWN"} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "DTYPE_CHANGED", "severity": "BLOCK", "column_name": "quantity"}
            ],
        },
        # Scenarios 15-17: Null rate spikes (WARN)
        {
            "id": "scenario_15_null_rate_spike_city",
            "name": "City null rate spike > 30% in erp_vendors",
            "contract": "erp_vendors.yaml",
            "source": "erp_vendors",
            "records": [
                {**r, "city": None if idx % 2 == 0 else r["city"]} for idx, r in enumerate(erp_base)
            ],
            "baseline": erp_base,
            "expected_events": [
                {"event_type": "NULL_RATE_SPIKE", "severity": "WARN", "column_name": "city"}
            ],
        },
        {
            "id": "scenario_16_null_rate_spike_postal_code",
            "name": "Postal code null rate spike > 30% in erp_vendors",
            "contract": "erp_vendors.yaml",
            "source": "erp_vendors",
            "records": [
                {**r, "postal_code": None if idx % 2 == 0 else r["postal_code"]}
                for idx, r in enumerate(erp_base)
            ],
            "baseline": erp_base,
            "expected_events": [
                {"event_type": "NULL_RATE_SPIKE", "severity": "WARN", "column_name": "postal_code"}
            ],
        },
        {
            "id": "scenario_17_null_rate_spike_notes_de",
            "name": "Notes_de null rate spike > 40% in quality_incidents",
            "contract": "quality_incidents.yaml",
            "source": "quality_incidents",
            "records": [
                {**r, "notes_de": None if idx % 2 == 0 else r["notes_de"]}
                for idx, r in enumerate(inc_base)
            ],
            "baseline": inc_base,
            "expected_events": [
                {"event_type": "NULL_RATE_SPIKE", "severity": "WARN", "column_name": "notes_de"}
            ],
        },
        # Scenarios 18-19: Numeric distribution p50 shifts (WARN)
        {
            "id": "scenario_18_p50_shift_unit_price",
            "name": "Unit price median p50 shifts > 50%",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "unit_price": 250.0} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "NUMERIC_P50_SHIFT", "severity": "WARN", "column_name": "unit_price"}
            ],
        },
        {
            "id": "scenario_19_p50_shift_quantity",
            "name": "Quantity median p50 shifts > 50%",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [{**r, "quantity": 500} for r in po_base],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "NUMERIC_P50_SHIFT", "severity": "WARN", "column_name": "quantity"}
            ],
        },
        # Scenario 20: New enum value (WARN)
        {
            "id": "scenario_20_new_enum_status",
            "name": "New enum value IN_DISPUTE appears in status",
            "contract": "purchase_orders.yaml",
            "source": "purchase_orders",
            "records": [
                {**r, "status": "IN_DISPUTE" if idx < 10 else r["status"]}
                for idx, r in enumerate(po_base)
            ],
            "baseline": po_base,
            "expected_events": [
                {"event_type": "NEW_ENUM_VALUE", "severity": "WARN", "column_name": "status"}
            ],
        },
    ]

    for sc in scenarios:
        s_dir = out_dir / sc["id"]
        s_dir.mkdir(parents=True, exist_ok=True)

        # Write current records CSV
        recs = sc["records"]
        if recs:
            with open(s_dir / "data.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
                writer.writeheader()
                writer.writerows(recs)

        # Write baseline CSV
        base_recs = sc.get("baseline", [])
        if base_recs:
            with open(s_dir / "baseline.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(base_recs[0].keys()))
                writer.writeheader()
                writer.writerows(base_recs)

        # Write scenario manifest
        manifest = {
            "id": sc["id"],
            "name": sc["name"],
            "contract": sc["contract"],
            "source": sc["source"],
            "expected_events": sc["expected_events"],
            "expected_mapping": sc.get("expected_mapping"),
        }
        with open(s_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    print(f"[SUCCESS] Created {len(scenarios)} drift scenarios in: {out_dir}")


if __name__ == "__main__":
    create_scenarios()
