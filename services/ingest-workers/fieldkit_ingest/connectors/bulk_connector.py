"""Bulk Connector for reference parquet datasets (GLEIF)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import duckdb

from fieldkit_ingest.connectors.base import Connector, IngestContext, RawBatch


class BulkConnector(Connector):
    """Streams reference Parquet datasets in chunks."""

    def __init__(
        self, file_path: str | Path = "data/ref/gleif_eu.parquet", source_id: str = "gleif_eu"
    ) -> None:
        self.file_path = Path(file_path)
        self.source_id = source_id

    async def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {self.file_path}")

        raw_bytes = self.file_path.read_bytes()
        con = duckdb.connect()

        # Query and iterate in batches
        con.execute(f"SELECT * FROM '{self.file_path.as_posix()}'")
        batch_no = 1
        cols = [desc[0] for desc in con.description]

        while True:
            rows = con.fetchmany(ctx.batch_size)
            if not rows:
                break
            records: list[dict[str, Any]] = [dict(zip(cols, r, strict=False)) for r in rows]
            for idx, r in enumerate(records, 1):
                r["_source_row_num"] = (batch_no - 1) * ctx.batch_size + idx

            yield RawBatch(
                source_id=self.source_id,
                batch_no=batch_no,
                raw_bytes=raw_bytes if batch_no == 1 else b"",
                records=records,
                source_row_ref=f"{self.file_path.name}:batch_{batch_no}",
            )
            batch_no += 1
