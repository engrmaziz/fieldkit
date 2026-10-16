"""CSV Connector with charset detection and delimiter sniffing."""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from charset_normalizer import from_bytes

from fieldkit_ingest.connectors.base import Connector, IngestContext, RawBatch


class CsvConnector(Connector):
    """Ingests delimited text files with automatic encoding and delimiter detection."""

    def __init__(self, file_path: str | Path, source_id: str | None = None) -> None:
        self.file_path = Path(file_path)
        self.source_id = source_id or self.file_path.stem

    async def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.file_path}")

        raw_bytes = self.file_path.read_bytes()

        # 1. Detect Encoding (prefer strict UTF-8, then Western European / Latin-1)
        text = ""
        encoding = "utf-8"
        try:
            text = raw_bytes.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            detected = from_bytes(raw_bytes).best()
            if (
                detected
                and detected.encoding
                and ("1252" in detected.encoding or "latin" in detected.encoding)
            ):
                encoding = detected.encoding
            else:
                encoding = "cp1252"
            text = raw_bytes.decode(encoding, errors="replace")

        # 2. Sniff Delimiter
        sample = text[:8192]
        delimiter = ";" if ";" in sample and sample.count(";") > sample.count(",") else ","
        try:
            sniffer = csv.Sniffer()
            sniffed = sniffer.sniff(sample, delimiters=";,\t|")
            delimiter = sniffed.delimiter
        except Exception:
            pass

        # 3. Parse Records in batches
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        batch_no = 1
        current_records: list[dict[str, Any]] = []

        for row_idx, row in enumerate(reader, 1):
            cleaned_row = {
                (k.strip() if k else f"col_{c_idx}"): (v.strip() if v else "")
                for c_idx, (k, v) in enumerate(row.items())
            }
            cleaned_row["_source_row_num"] = row_idx
            current_records.append(cleaned_row)

            if len(current_records) >= ctx.batch_size:
                yield RawBatch(
                    source_id=self.source_id,
                    batch_no=batch_no,
                    raw_bytes=raw_bytes if batch_no == 1 else b"",
                    records=current_records,
                    source_row_ref=f"{self.file_path.name}:{row_idx - len(current_records) + 1}-{row_idx}",
                    metadata={
                        "encoding": encoding,
                        "delimiter": delimiter,
                        "total_sample": len(sample),
                    },
                )
                batch_no += 1
                current_records = []

        if current_records or batch_no == 1:
            yield RawBatch(
                source_id=self.source_id,
                batch_no=batch_no,
                raw_bytes=raw_bytes if batch_no == 1 else b"",
                records=current_records,
                source_row_ref=f"{self.file_path.name}:end",
                metadata={"encoding": encoding, "delimiter": delimiter},
            )
