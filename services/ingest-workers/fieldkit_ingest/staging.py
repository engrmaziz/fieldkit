"""Staging database manager writing to data/staging/<run_id>.duckdb."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa


class StagingStore:
    """Manages the typed, clean DuckDB staging warehouse per ingest run."""

    def __init__(self, run_id: str, staging_dir: str | Path = "data/staging") -> None:
        self.run_id = run_id
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.staging_dir / f"{run_id}.duckdb"

    def write_records(self, table_name: str, records: list[dict[str, Any]]) -> int:
        """Appends validated records to the staging table. Returns count written."""
        if not records:
            return 0

        # Remove internal tracking fields before writing to clean staging
        clean_rows = []
        for r in records:
            row_copy = {k: v for k, v in r.items() if not k.startswith("_")}
            clean_rows.append(row_copy)

        table = pa.Table.from_pylist(clean_rows)
        con = duckdb.connect(self.db_path.as_posix())

        con.register("new_records", table)
        con.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM new_records WHERE 1=0;"
        )
        con.execute(f"INSERT INTO {table_name} SELECT * FROM new_records;")
        count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        con.close()
        return count

    def get_table_counts(self) -> dict[str, int]:
        """Returns row counts for all tables in the staging DuckDB."""
        if not self.db_path.exists():
            return {}
        con = duckdb.connect(self.db_path.as_posix())
        tables = con.execute("SHOW TABLES").fetchall()
        counts = {}
        for (t_name,) in tables:
            c = con.execute(f"SELECT count(*) FROM {t_name}").fetchone()[0]
            counts[t_name] = c
        con.close()
        return counts
