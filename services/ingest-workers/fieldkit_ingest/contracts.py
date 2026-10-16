"""Contract loader and validator using runtime schemas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ValidationResult:
    valid_records: list[dict[str, Any]]
    quarantined_records: list[dict[str, Any]]


class ContractValidator:
    """Validates raw records against source YAML contracts with date/decimal normalization."""

    def __init__(
        self,
        contract_path: str | Path,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self.contract_path = Path(contract_path)
        self.config = self._load_contract()
        self.columns = self.config.get("columns", {})
        self.overrides = overrides or {}

    def _load_contract(self) -> dict[str, Any]:
        if not self.contract_path.exists():
            raise FileNotFoundError(f"Contract YAML not found at: {self.contract_path}")
        with open(self.contract_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _parse_date(self, val: str, formats: list[str]) -> str | None:
        if not val:
            return None
        val_clean = val.strip()
        for fmt in formats:
            try:
                dt = datetime.strptime(val_clean, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _parse_float(self, val: Any, locale: str = "en") -> float | None:
        if val is None or val == "":
            return None
        if isinstance(val, (int, float)):
            return float(val)

        s = str(val).strip()
        if locale == "de":
            # Convert German format: 1.250,50 -> 1250.50 or 1250,50 -> 1250.50
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")

        try:
            return float(s)
        except ValueError:
            return None

    def validate_batch(
        self,
        records: list[dict[str, Any]],
        source_name: str,
        run_id: str,
    ) -> ValidationResult:
        valid_records: list[dict[str, Any]] = []
        quarantined: list[dict[str, Any]] = []

        for row in records:
            row_ref = f"{source_name}:row_{row.get('_source_row_num', '?')}"
            cleaned_row = dict(row)
            if self.overrides:
                for expected_col, actual_col in self.overrides.items():
                    if actual_col in cleaned_row and expected_col not in cleaned_row:
                        cleaned_row[expected_col] = cleaned_row[actual_col]

            rejection_reasons: list[str] = []

            for col_name, spec in self.columns.items():
                col_type = spec.get("type", "str")
                required = spec.get("required", False)
                nullable = spec.get("nullable", True)
                locale = spec.get("locale", "en")
                date_formats = spec.get("date_formats", ["%Y-%m-%d", "%d.%m.%Y", "%m/%d/%y"])

                val = cleaned_row.get(col_name)

                # Required check
                if required and (val is None or str(val).strip() == ""):
                    if not nullable:
                        rejection_reasons.append(
                            f"Missing non-nullable required field: '{col_name}'"
                        )
                        continue

                # Type parsing
                if val is not None and str(val).strip() != "":
                    if col_type == "float":
                        parsed_num = self._parse_float(val, locale=locale)
                        if parsed_num is None:
                            rejection_reasons.append(
                                f"Invalid decimal value '{val}' for column '{col_name}'"
                            )
                        else:
                            cleaned_row[col_name] = parsed_num
                    elif col_type == "int":
                        try:
                            cleaned_row[col_name] = int(str(val).replace(".", "").replace(",", ""))
                        except ValueError:
                            rejection_reasons.append(
                                f"Invalid integer value '{val}' for column '{col_name}'"
                            )
                    elif col_type == "date":
                        parsed_dt = self._parse_date(str(val), date_formats)
                        if not parsed_dt:
                            rejection_reasons.append(
                                f"Unrecognized date format '{val}' for column '{col_name}'"
                            )
                        else:
                            cleaned_row[col_name] = parsed_dt
                    else:
                        cleaned_row[col_name] = str(val).strip()

            if rejection_reasons:
                quarantined.append(
                    {
                        "run_id": run_id,
                        "source": source_name,
                        "row_ref": row_ref,
                        "reason": "; ".join(rejection_reasons),
                        "raw_record": row,
                    }
                )
            else:
                valid_records.append(cleaned_row)

        return ValidationResult(valid_records=valid_records, quarantined_records=quarantined)
