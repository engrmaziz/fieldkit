"""PDF Connector for tracking contract and invoice PDF file metadata."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fieldkit_ingest.connectors.base import Connector, IngestContext, RawBatch


class PdfConnector(Connector):
    """Scans and registers contract PDF document metadata without parsing text."""

    def __init__(
        self, dir_path: str | Path = "data/raw/contracts", source_id: str = "contracts_pdf"
    ) -> None:
        self.dir_path = Path(dir_path)
        self.source_id = source_id

    async def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        records: list[dict[str, Any]] = []
        batch_no = 1

        if self.dir_path.exists():
            pdf_files = list(self.dir_path.glob("**/*.pdf"))
            for idx, pdf_file in enumerate(pdf_files, 1):
                stat = pdf_file.stat()
                file_bytes = pdf_file.read_bytes()
                sha256 = hashlib.sha256(file_bytes).hexdigest()

                records.append(
                    {
                        "file_path": str(pdf_file),
                        "file_name": pdf_file.name,
                        "file_size_bytes": stat.st_size,
                        "sha256": sha256,
                        "modified_at": stat.st_mtime,
                        "_source_row_num": idx,
                    }
                )

                if len(records) >= ctx.batch_size:
                    yield RawBatch(
                        source_id=self.source_id,
                        batch_no=batch_no,
                        raw_bytes=b"",
                        records=records,
                        source_row_ref=f"pdf:{idx - len(records) + 1}-{idx}",
                    )
                    batch_no += 1
                    records = []

        if records or batch_no == 1:
            yield RawBatch(
                source_id=self.source_id,
                batch_no=batch_no,
                raw_bytes=b"",
                records=records,
                source_row_ref="pdf:end",
            )
