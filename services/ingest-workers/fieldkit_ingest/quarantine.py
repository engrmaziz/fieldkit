"""Quarantine store and Ingest Run tracker."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import psycopg


class QuarantineManager:
    """Manages rejected records quarantine table and ingest run execution records."""

    def __init__(
        self,
        postgres_dsn: str | None = None,
        fallback_dir: str | Path = "data/staging",
    ) -> None:
        self.postgres_dsn = postgres_dsn or os.getenv(
            "DATABASE_URL",
            "postgresql://fieldkit:fieldkit_dev_insecure@localhost:5432/fieldkit",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.fallback_path = Path(fallback_dir) / "quarantine.duckdb"
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._use_postgres = self._init_postgres()

    def _init_postgres(self) -> bool:
        try:
            with psycopg.connect(self.postgres_dsn, autocommit=True, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS ingest_run (
                            run_id VARCHAR(64) PRIMARY KEY,
                            source VARCHAR(64) NOT NULL,
                            started_at TIMESTAMP NOT NULL,
                            finished_at TIMESTAMP,
                            rows_in INT DEFAULT 0,
                            rows_ok INT DEFAULT 0,
                            rows_quarantined INT DEFAULT 0,
                            status VARCHAR(32) NOT NULL
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS quarantine (
                            id SERIAL PRIMARY KEY,
                            run_id VARCHAR(64) NOT NULL,
                            source VARCHAR(64) NOT NULL,
                            row_ref VARCHAR(128) NOT NULL,
                            reason TEXT NOT NULL,
                            raw_record JSONB NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
            return True
        except Exception:
            # Fallback to duckdb
            con = duckdb.connect(self.fallback_path.as_posix())
            con.execute("""
                CREATE TABLE IF NOT EXISTS ingest_run (
                    run_id VARCHAR,
                    source VARCHAR,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    rows_in BIGINT,
                    rows_ok BIGINT,
                    rows_quarantined BIGINT,
                    status VARCHAR
                );
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS quarantine (
                    run_id VARCHAR,
                    source VARCHAR,
                    row_ref VARCHAR,
                    reason VARCHAR,
                    raw_record VARCHAR,
                    created_at TIMESTAMP
                );
            """)
            con.close()
            return False

    def log_run_start(self, run_id: str, source: str) -> None:
        now = datetime.now()
        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO ingest_run (run_id, source, started_at, status) VALUES (%s, %s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
                            (run_id, source, now, "RUNNING"),
                        )
                return
            except Exception:
                pass

        con = duckdb.connect(self.fallback_path.as_posix())
        con.execute(
            "INSERT INTO ingest_run VALUES (?, ?, ?, NULL, 0, 0, 0, ?)",
            (run_id, source, now, "RUNNING"),
        )
        con.close()

    def record_quarantine(self, quarantined_records: list[dict[str, Any]]) -> None:
        if not quarantined_records:
            return

        now = datetime.now()
        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        for q in quarantined_records:
                            cur.execute(
                                "INSERT INTO quarantine (run_id, source, row_ref, reason, raw_record, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                                (
                                    q["run_id"],
                                    q["source"],
                                    q["row_ref"],
                                    q["reason"],
                                    json.dumps(q["raw_record"]),
                                    now,
                                ),
                            )
                return
            except Exception:
                pass

        con = duckdb.connect(self.fallback_path.as_posix())
        for q in quarantined_records:
            con.execute(
                "INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?)",
                (
                    q["run_id"],
                    q["source"],
                    q["row_ref"],
                    q["reason"],
                    json.dumps(q["raw_record"]),
                    now,
                ),
            )
        con.close()

    def log_run_finish(
        self,
        run_id: str,
        rows_in: int,
        rows_ok: int,
        rows_quarantined: int,
        status: str = "SUCCESS",
    ) -> None:
        now = datetime.now()
        if self._use_postgres:
            try:
                with psycopg.connect(self.postgres_dsn, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE ingest_run SET finished_at = %s, rows_in = %s, rows_ok = %s, rows_quarantined = %s, status = %s WHERE run_id = %s",
                            (now, rows_in, rows_ok, rows_quarantined, status, run_id),
                        )
                return
            except Exception:
                pass

        con = duckdb.connect(self.fallback_path.as_posix())
        con.execute(
            "UPDATE ingest_run SET finished_at = ?, rows_in = ?, rows_ok = ?, rows_quarantined = ?, status = ? WHERE run_id = ?",
            (now, rows_in, rows_ok, rows_quarantined, status, run_id),
        )
        con.close()
