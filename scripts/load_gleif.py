"""Stream zipped GLEIF CSV with DuckDB, filter EU countries, and write Parquet.

Target Countries: DE (Germany), PL (Poland), AT (Austria), CZ (Czech Republic).
Output: data/ref/gleif_eu.parquet
"""

import time
from pathlib import Path

import duckdb

INPUT_ZIP = Path("data/raw/gleif/gleif-goldencopy-lei2-golden-copy.csv.zip")
OUTPUT_PARQUET = Path("data/ref/gleif_eu.parquet")


def load_gleif() -> None:
    if not INPUT_ZIP.exists():
        raise FileNotFoundError(f"GLEIF zip archive not found at: {INPUT_ZIP}")

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    print(f"Streaming and filtering GLEIF Golden Copy from:\n  {INPUT_ZIP}")
    print("Target EU countries: DE, PL, AT, CZ")
    print(f"Writing output to:\n  {OUTPUT_PARQUET}...")

    start_time = time.perf_counter()
    extracted_csv: Path | None = None

    # Check if uncompressed CSV already exists or extract from zip
    import zipfile

    with zipfile.ZipFile(INPUT_ZIP, "r") as z:
        csv_names = [n for n in z.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV file found inside {INPUT_ZIP}")
        target_csv_name = csv_names[0]
        candidate_csv = INPUT_ZIP.parent / target_csv_name

        if candidate_csv.exists():
            csv_path = candidate_csv
            print(f"Using existing extracted CSV: {csv_path}")
        else:
            print(f"Extracting {target_csv_name} from archive...")
            z.extract(target_csv_name, path=INPUT_ZIP.parent)
            csv_path = candidate_csv
            extracted_csv = candidate_csv

    con = duckdb.connect()

    # Stream CSV into Parquet
    query = f"""
    COPY (
        SELECT
            LEI AS lei,
            "Entity.LegalName" AS legal_name,
            COALESCE("Entity.LegalForm.EntityLegalFormCode", "Entity.LegalForm.OtherLegalForm", '') AS legal_form,
            COALESCE("Entity.LegalAddress.FirstAddressLine", '') AS street,
            COALESCE("Entity.LegalAddress.City", '') AS city,
            COALESCE("Entity.LegalAddress.PostalCode", '') AS postcode,
            "Entity.LegalAddress.Country" AS country
        FROM read_csv(
            '{csv_path.as_posix()}',
            header=true,
            all_varchar=true,
            ignore_errors=true
        )
        WHERE "Entity.LegalAddress.Country" IN ('DE', 'PL', 'AT', 'CZ')
          AND "Entity.LegalName" IS NOT NULL
    ) TO '{OUTPUT_PARQUET.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    con.execute(query)

    # Clean up large extracted CSV to preserve disk space if we extracted it
    if extracted_csv and extracted_csv.exists():
        print(f"Cleaning up temporary extracted CSV {extracted_csv}...")
        try:
            extracted_csv.unlink()
        except Exception as e:
            print(f"Warning: Failed to delete {extracted_csv}: {e}")
    elapsed = time.perf_counter() - start_time

    # Inspect results
    count_res = con.execute(f"SELECT count(*) FROM '{OUTPUT_PARQUET.as_posix()}'").fetchone()
    total_rows = count_res[0] if count_res else 0

    country_breakdown = con.execute(
        f"SELECT country, count(*) FROM '{OUTPUT_PARQUET.as_posix()}' GROUP BY country ORDER BY count(*) DESC"
    ).fetchall()

    file_size_mb = OUTPUT_PARQUET.stat().st_size / (1024 * 1024)

    print(f"\n[SUCCESS] Extraction completed successfully in {elapsed:.2f} seconds.")
    print(f"  - Total rows written: {total_rows:,}")
    print(f"  - Parquet size: {file_size_mb:.2f} MB")
    print("  - Country distribution:")
    for country, count in country_breakdown:
        print(f"      {country}: {count:,}")


if __name__ == "__main__":
    load_gleif()
