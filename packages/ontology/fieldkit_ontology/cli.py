"""CLI tool for Fieldkit Enterprise Ontology codegen and promotion."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fieldkit_ontology.codegen import generate_all
from fieldkit_ontology.promote import OntologyPromoter
from fieldkit_ontology.spec import load_ontology_spec


async def _run_promotion(staging_db: str | Path, run_id: str | None = None) -> None:
    db_path = Path(staging_db)
    if not db_path.exists():
        print(f"Error: Staging database '{staging_db}' does not exist.")
        sys.exit(1)

    actual_run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/fieldkit",
    )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"[*] Promoting staging DuckDB '{db_path}' -> PostgreSQL ontology...")
    print(f"    Target Run ID: {actual_run_id}")

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    promoter = OntologyPromoter(db_path)
    async with session_factory() as session:
        metrics = await promoter.promote(session, run_id=actual_run_id)
        await session.commit()

    await engine.dispose()

    print("[+] Promotion Completed:")
    print(f"    - Inserted:  {metrics['inserted']}")
    print(f"    - Updated:   {metrics['updated']}")
    print(f"    - Unchanged: {metrics['unchanged']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fieldkit Ontology CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Codegen command
    codegen_parser = subparsers.add_parser(
        "codegen", help="Generate models, schemas, and migrations"
    )
    codegen_parser.add_argument("--spec", help="Path to ontology.yaml", default=None)
    codegen_parser.add_argument("--out", help="Output directory for generated files", default=None)

    # Promote command
    promote_parser = subparsers.add_parser(
        "promote", help="Promote staged DuckDB records to PostgreSQL ontology"
    )
    promote_parser.add_argument("--staging-db", required=True, help="Path to staging DuckDB file")
    promote_parser.add_argument(
        "--run-id", default=None, help="Explicit run ID (generated if not provided)"
    )

    args = parser.parse_args()

    if args.command == "codegen":
        spec_path = Path(args.spec) if args.spec else None
        out_dir = Path(args.out) if args.out else None
        spec = load_ontology_spec(spec_path) if spec_path else None
        generate_all(spec=spec, output_dir=out_dir)
        print("Ontology code generation completed successfully.")

    elif args.command == "promote":
        asyncio.run(_run_promotion(args.staging_db, args.run_id))


if __name__ == "__main__":
    main()
