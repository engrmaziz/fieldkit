"""Fieldkit Ingest CLI and pipeline coordinator."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fieldkit_common.otel import get_tracer

from fieldkit_ingest.connectors.base import Connector, IngestContext
from fieldkit_ingest.connectors.csv_connector import CsvConnector
from fieldkit_ingest.connectors.excel_connector import ExcelConnector
from fieldkit_ingest.contracts import ContractValidator
from fieldkit_ingest.drift import (
    DriftEventType,
    DriftRuleEngine,
    DriftSeverity,
    DriftStore,
    LLMRenameSuggester,
    compute_fingerprint,
)
from fieldkit_ingest.landing import LandingZone
from fieldkit_ingest.quarantine import QuarantineManager
from fieldkit_ingest.staging import StagingStore

tracer = get_tracer("fieldkit-ingest")


def get_contracts_dir() -> Path:
    # Look for contracts in services/ingest-workers/contracts or parent
    candidates = [
        Path(__file__).parent.parent / "contracts",
        Path("services/ingest-workers/contracts"),
        Path("contracts"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("services/ingest-workers/contracts")


class IngestPipeline:
    """Coordinates landing, contract validation, quarantine routing, and staging store."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.landing = LandingZone()
        self.staging = StagingStore(run_id=self.run_id)
        self.quarantine_mgr = QuarantineManager()
        self.drift_store = DriftStore()
        self.llm_suggester = LLMRenameSuggester()
        self.contracts_dir = get_contracts_dir()

    async def ingest_source(
        self,
        source_id: str,
        connector: Connector,
        contract_file: str | None,
        staging_table: str,
    ) -> dict[str, Any]:
        with tracer.start_as_current_span(f"ingest.{source_id}") as span:
            span.set_attribute("source_id", source_id)
            span.set_attribute("run_id", self.run_id)

            self.quarantine_mgr.log_run_start(f"{self.run_id}_{source_id}", source_id)
            ctx = IngestContext(run_id=self.run_id, source_name=source_id, batch_size=5000)

            # Drift detection & override resolution
            active_overrides_raw = self.drift_store.get_active_overrides(source_id)
            overrides_for_source = {
                k.split(":", 1)[1]: v
                for k, v in active_overrides_raw.items()
                if k.startswith(f"{source_id}:")
            }

            validator = None
            contract_cols: dict[str, Any] = {}
            if contract_file:
                c_path = self.contracts_dir / contract_file
                if c_path.exists():
                    validator = ContractValidator(c_path, overrides=overrides_for_source)
                    contract_cols = validator.columns

            total_in = 0
            total_ok = 0
            total_quarantined = 0
            newly_landed = False

            async for batch in connector.extract(ctx):
                # 1. Landing raw bytes immutably (if bytes present)
                if batch.raw_bytes:
                    _, _, skipped = self.landing.land(
                        source=source_id,
                        run_id=self.run_id,
                        filename=f"{source_id}.raw",
                        raw_bytes=batch.raw_bytes,
                    )
                    if not skipped:
                        newly_landed = True

                total_in += len(batch.records)

                # 2. Schema and statistical drift detection
                fp = compute_fingerprint(batch.records, source=source_id, run_id=self.run_id)
                rule_engine = DriftRuleEngine(overrides=active_overrides_raw)
                drift_events = rule_engine.evaluate(current=fp, contract_columns=contract_cols)

                # Propose column rename suggestion if a required column is removed and an unexpected one added
                removed_events = [
                    e for e in drift_events if e.event_type == DriftEventType.COLUMN_REMOVED
                ]
                added_events = [
                    e for e in drift_events if e.event_type == DriftEventType.COLUMN_ADDED
                ]

                if removed_events and added_events:
                    for rem_e in removed_events:
                        for add_e in added_events:
                            old_col = rem_e.column_name
                            new_col = add_e.column_name
                            old_dtype = contract_cols.get(old_col, {}).get("type", "str")
                            new_dtype = next(
                                (c["dtype"] for c in fp.columns if c["name"] == new_col), "string"
                            )
                            new_samples = [
                                str(r.get(new_col, ""))
                                for r in batch.records[:20]
                                if r.get(new_col)
                            ]
                            try:
                                suggestion = await self.llm_suggester.suggest_rename(
                                    source_name=source_id,
                                    old_col=old_col,
                                    old_dtype=old_dtype,
                                    old_samples=[],
                                    new_col=new_col,
                                    new_dtype=new_dtype,
                                    new_samples=new_samples,
                                )
                                rem_e.suggestion = suggestion
                                rem_e.status = "suggested"
                            except Exception:
                                pass

                if drift_events:
                    self.drift_store.save_events(drift_events)

                blocked_events = [e for e in drift_events if e.severity == DriftSeverity.BLOCK]
                if blocked_events:
                    for be in blocked_events:
                        print(
                            f"    [DRIFT BLOCK] {be.event_type.value} on '{be.column_name}': {be.details.get('message')}"
                        )
                    self.quarantine_mgr.log_run_finish(
                        run_id=f"{self.run_id}_{source_id}",
                        rows_in=len(batch.records),
                        rows_ok=0,
                        rows_quarantined=0,
                        status="BLOCKED_DRIFT",
                    )
                    return {
                        "source": source_id,
                        "rows_in": len(batch.records),
                        "rows_ok": 0,
                        "rows_quarantined": 0,
                        "newly_landed": newly_landed,
                        "staging_table": staging_table,
                        "blocked": True,
                        "drift_events": [asdict(e) for e in drift_events],
                    }

                warn_events = [e for e in drift_events if e.severity == DriftSeverity.WARN]
                for we in warn_events:
                    print(
                        f"    [DRIFT WARN] {we.event_type.value} on '{we.column_name}': {we.details.get('message')}"
                    )

                # 3. Contract validation
                if validator:
                    res = validator.validate_batch(
                        records=batch.records,
                        source_name=source_id,
                        run_id=self.run_id,
                    )
                    valid_recs = res.valid_records
                    quarantine_recs = res.quarantined_records
                else:
                    valid_recs = batch.records
                    quarantine_recs = []

                total_ok += len(valid_recs)
                total_quarantined += len(quarantine_recs)

                # 4. Route quarantine
                if quarantine_recs:
                    self.quarantine_mgr.record_quarantine(quarantine_recs)

                # 5. Write valid records to staging DuckDB
                if valid_recs:
                    self.staging.write_records(staging_table, valid_recs)

            self.quarantine_mgr.log_run_finish(
                run_id=f"{self.run_id}_{source_id}",
                rows_in=total_in,
                rows_ok=total_ok,
                rows_quarantined=total_quarantined,
                status="SUCCESS",
            )

            span.set_attribute("rows_in", total_in)
            span.set_attribute("rows_ok", total_ok)
            span.set_attribute("rows_quarantined", total_quarantined)

            return {
                "source": source_id,
                "rows_in": total_in,
                "rows_ok": total_ok,
                "rows_quarantined": total_quarantined,
                "newly_landed": newly_landed,
                "staging_table": staging_table,
                "blocked": False,
            }


async def run_pipeline(
    source: str = "all",
    run_id: str | None = None,
    with_er: bool = True,
    promote: bool = False,
) -> None:

    start_time = time.perf_counter()
    pipeline = IngestPipeline(run_id=run_id)

    print("\n========================================================")
    print(f"  Fieldkit Ingest Run: {pipeline.run_id}")
    print(f"  Target Source(s): {source}")
    print("========================================================\n")

    # Define registered sources
    sources_to_run: list[tuple[str, Connector, str | None, str]] = []

    # 1. ERP Vendors
    if source in ("all", "erp_vendors"):
        erp_csv = Path("data/raw/erp/erp_vendors.csv")
        if erp_csv.exists():
            sources_to_run.append(
                (
                    "erp_vendors",
                    CsvConnector(erp_csv, source_id="erp_vendors"),
                    "erp_vendors.yaml",
                    "stg_erp_vendors",
                )
            )

    # 2. Excel Hamburg
    if source in ("all", "excel", "planning_ham"):
        ham_xlsx = Path("data/raw/excel/planning_de_ham.xlsx")
        if ham_xlsx.exists():
            sources_to_run.append(
                (
                    "planning_de_ham",
                    ExcelConnector(ham_xlsx, source_id="planning_de_ham"),
                    "planning_excel.yaml",
                    "stg_planning_excel",
                )
            )

    # 3. Excel Stralsund
    if source in ("all", "excel", "planning_str"):
        str_xlsx = Path("data/raw/excel/planning_de_str.xlsx")
        if str_xlsx.exists():
            sources_to_run.append(
                (
                    "planning_de_str",
                    ExcelConnector(str_xlsx, source_id="planning_de_str"),
                    "planning_excel.yaml",
                    "stg_planning_excel",
                )
            )

    # 4. SOAP Supplier Certificates
    if source in ("all", "soap", "soap_seed"):
        soap_seed_file = Path("data/raw/soap/soap_seed.json")
        if soap_seed_file.exists():
            # In offline or standalone mode, simulate SOAP connector using the generated seed
            class LocalSoapConnector(Connector):
                async def extract(self, ctx: IngestContext):  # noqa: ANN201
                    raw_b = soap_seed_file.read_bytes()
                    data = json.loads(raw_b)
                    flat_records = []
                    for idx, r in enumerate(data, 1):
                        certs = r.get("certifications", [{}])
                        c = certs[0] if certs else {}
                        flat_records.append(
                            {
                                "soap_vendor_id": r.get("soap_vendor_id", ""),
                                "company_name": r.get("company_name", ""),
                                "status": c.get("audit_status", "ACTIVE"),
                                "standard": c.get("standard", "ISO 9001:2015"),
                                "certificate_id": c.get("certificate_id", ""),
                                "issued_date": c.get("issued_date", ""),
                                "expiry_date": c.get("expiry_date", ""),
                                "_source_row_num": idx,
                            }
                        )
                    from fieldkit_ingest.connectors.base import RawBatch

                    yield RawBatch(
                        source_id="soap_seed",
                        batch_no=1,
                        raw_bytes=raw_b,
                        records=flat_records,
                        source_row_ref="soap_seed.json:all",
                    )

            sources_to_run.append(
                (
                    "soap_seed",
                    LocalSoapConnector(),
                    "soap_certs.yaml",
                    "stg_soap_certs",
                )
            )

    # 5. Purchase Orders
    if source in ("all", "purchase_orders"):
        po_csv = Path("data/raw/erp/purchase_orders.csv")
        if po_csv.exists():
            sources_to_run.append(
                (
                    "purchase_orders",
                    CsvConnector(po_csv, source_id="purchase_orders"),
                    "purchase_orders.yaml",
                    "stg_purchase_orders",
                )
            )

    # 6. Quality Incidents
    if source in ("all", "quality_incidents"):
        inc_csv = Path("data/raw/erp/quality_incidents.csv")
        if inc_csv.exists():
            sources_to_run.append(
                (
                    "quality_incidents",
                    CsvConnector(inc_csv, source_id="quality_incidents"),
                    "quality_incidents.yaml",
                    "stg_quality_incidents",
                )
            )

    if not sources_to_run:
        print(f"No active data sources found for '{source}'. Run scripts/gen_erp.py first.")
        return

    results = []
    for s_id, conn, c_yaml, stg_table in sources_to_run:
        print(f"[*] Ingesting: {s_id} -> {stg_table}...")
        res = await pipeline.ingest_source(s_id, conn, c_yaml, stg_table)
        q_rate = (res["rows_quarantined"] / max(res["rows_in"], 1)) * 100.0
        status_flag = "NEW" if res["newly_landed"] else "LANDED"
        print(
            f"    [+] In: {res['rows_in']:,} | Valid: {res['rows_ok']:,} | Quarantined: {res['rows_quarantined']:,} ({q_rate:.2f}%) [{status_flag}]"
        )
        results.append(res)

    # 7. Entity Resolution (Canonicalization of Suppliers)
    if with_er and any(
        r["source"] in ("erp_vendors", "planning_de_ham", "planning_de_str") for r in results
    ):
        print("[*] Running Supplier Entity Resolution & Canonicalization (packages/er)...")
        from fieldkit_ingest.resolve import resolve_staged_suppliers

        er_metrics = resolve_staged_suppliers(pipeline.staging, pipeline.run_id)
        print(
            f"    [+] Canonical Suppliers: {er_metrics['canonical_count']:,} resolved "
            f"from {er_metrics['total_raw']:,} raw records ({er_metrics['clusters_count']:,} clusters) -> stg_canonical_suppliers"
        )

    # 8. Promotion to PostgreSQL Ontology
    if promote:
        print("[*] Promoting Staged Records to PostgreSQL Ontology (packages/ontology)...")
        from fieldkit_ontology.cli import _run_promotion

        await _run_promotion(pipeline.staging.db_path, run_id=pipeline.run_id)

    elapsed = time.perf_counter() - start_time
    total_in = sum(r["rows_in"] for r in results)
    total_ok = sum(r["rows_ok"] for r in results)
    total_quarantine = sum(r["rows_quarantined"] for r in results)
    overall_q_rate = (total_quarantine / max(total_in, 1)) * 100.0

    print("\n--------------------------------------------------------")
    print(f"[SUCCESS] Ingest Run Completed in {elapsed:.2f}s")
    print(f"  - Total Rows Processed:   {total_in:,}")
    print(f"  - Valid Staged Rows:      {total_ok:,}")
    print(f"  - Quarantined Rows:       {total_quarantine:,} ({overall_q_rate:.2f}%)")
    print(f"  - Staging DuckDB Path:    {pipeline.staging.db_path}")
    print("--------------------------------------------------------\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fieldkit Enterprise Ingest CLI")
    parser.add_argument(
        "command", choices=["run"], default="run", nargs="?", help="Command to execute"
    )
    parser.add_argument(
        "--source",
        default="all",
        help="Source to ingest: erp_vendors, excel, soap, purchase_orders, quality_incidents, or all",
    )
    parser.add_argument("--run-id", default=None, help="Explicit run ID for tracking and staging")
    parser.add_argument(
        "--skip-er",
        action="store_true",
        help="Skip entity resolution post-processing step",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote staged records into PostgreSQL ontology after ingest",
    )
    args = parser.parse_args()

    asyncio.run(
        run_pipeline(
            source=args.source,
            run_id=args.run_id,
            with_er=not args.skip_er,
            promote=args.promote,
        )
    )


if __name__ == "__main__":
    main()
