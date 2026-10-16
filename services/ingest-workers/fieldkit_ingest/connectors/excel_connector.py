"""Excel Connector for messy enterprise plant planning spreadsheets."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import openpyxl

from fieldkit_ingest.connectors.base import Connector, IngestContext, RawBatch


class ExcelConnector(Connector):
    """Ingests multi-row header, formatted Excel planning workbooks."""

    def __init__(self, file_path: str | Path, source_id: str | None = None) -> None:
        self.file_path = Path(file_path)
        self.source_id = source_id or self.file_path.stem

    async def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")

        raw_bytes = self.file_path.read_bytes()

        # Load workbook (data_only=False to inspect formulas if needed)
        wb = openpyxl.load_workbook(self.file_path, data_only=True)
        ws = wb.active

        # Identify hidden rows
        hidden_rows = {row_idx for row_idx, dim in ws.row_dimensions.items() if dim.hidden}

        # 1. Unmerge merged cell ranges so values populate across merged bounds
        for merged_range in list(ws.merged_cells.ranges):
            min_col, min_row, max_col, max_row = merged_range.bounds
            top_val = ws.cell(row=min_row, column=min_col).value
            ws.unmerge_cells(str(merged_range))
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    ws.cell(row=r, column=c).value = top_val

        # 2. Locate header row:
        # Halden spreadsheets have title banners on rows 1-2, category banners on row 3,
        # and actual column headers on row 4.
        header_row_idx = 4
        # Search specifically for the row containing column header keywords
        for r_idx in range(1, 10):
            row_vals = [str(ws.cell(row=r_idx, column=c).value or "").strip() for c in range(1, 15)]
            if any(
                "Lieferanten-Nr" in v
                or "Vendor_ID" in v
                or "Vendor ID" in v
                or "Lieferanten_Nr" in v
                for v in row_vals
            ):
                header_row_idx = r_idx
                break

        headers: list[str] = []
        max_col = ws.max_column or 1
        for col_idx in range(1, max_col + 1):
            val = ws.cell(row=header_row_idx, column=col_idx).value
            h_name = str(val).strip() if val is not None else f"col_{col_idx}"
            headers.append(h_name)

        # 3. Read data rows, skipping hidden rows and totals rows
        records: list[dict[str, Any]] = []
        batch_no = 1
        max_row = ws.max_row or header_row_idx

        for r_idx in range(header_row_idx + 1, max_row + 1):
            # Skip hidden rows
            if r_idx in hidden_rows:
                continue

            first_col_val = str(ws.cell(row=r_idx, column=1).value or "").strip()
            # Drop totals row
            if "GESAMT" in first_col_val.upper() or "TOTAL" in first_col_val.upper():
                continue

            # Check if entire row is empty
            row_dict: dict[str, Any] = {}
            has_val = False
            for c_idx, h in enumerate(headers, 1):
                cell_val = ws.cell(row=r_idx, column=c_idx).value
                if cell_val is not None and str(cell_val).strip() != "":
                    has_val = True
                row_dict[h] = str(cell_val).strip() if cell_val is not None else ""

            if not has_val:
                continue

            row_dict["_source_row_num"] = r_idx
            records.append(row_dict)

            if len(records) >= ctx.batch_size:
                yield RawBatch(
                    source_id=self.source_id,
                    batch_no=batch_no,
                    raw_bytes=raw_bytes if batch_no == 1 else b"",
                    records=records,
                    source_row_ref=f"{self.file_path.name}:{r_idx - len(records) + 1}-{r_idx}",
                    metadata={"sheet": ws.title, "header_row": header_row_idx},
                )
                batch_no += 1
                records = []

        if records or batch_no == 1:
            yield RawBatch(
                source_id=self.source_id,
                batch_no=batch_no,
                raw_bytes=raw_bytes if batch_no == 1 else b"",
                records=records,
                source_row_ref=f"{self.file_path.name}:end",
                metadata={"sheet": ws.title, "header_row": header_row_idx},
            )
