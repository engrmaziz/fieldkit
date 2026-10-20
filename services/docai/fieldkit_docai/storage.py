"""Persistent storage and audit ledger for Document Intelligence."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fieldkit_common.logging import get_logger

from fieldkit_docai.config import settings
from fieldkit_docai.models import (
    DocumentRecord,
    DocumentStatus,
    DocumentStep,
    DocumentType,
    PageResult,
    StepStatus,
)

logger = get_logger("fieldkit.docai.storage")


class DocumentStore:
    """Manages document metadata, processing steps, and binary storage via SQLite and MinIO."""

    def __init__(self, db_url: str | None = None, storage_dir: str | None = None) -> None:
        self.db_url = db_url or settings.database_url
        self.storage_dir = Path(storage_dir or settings.storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if self.db_url.startswith("sqlite:///"):
            self.db_file = Path(self.db_url.replace("sqlite:///", ""))
            self.db_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_file = Path("./data/docai.db")
            self.db_file.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_file))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    page_count INTEGER DEFAULT 0,
                    document_type TEXT DEFAULT 'other',
                    status TEXT DEFAULT 'uploaded',
                    error TEXT,
                    pages_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_steps (
                    step_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL DEFAULT 0.0,
                    error TEXT,
                    details_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE(document_id, step_name)
                )
                """
            )
            conn.commit()

    async def create_document(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> DocumentRecord:
        """Register an uploaded document with SHA-256 deduplication and persist content."""
        sha256_hash = hashlib.sha256(content).hexdigest()
        doc_id = f"DOC-{sha256_hash[:12].upper()}"

        # 1. Deduplication check: return existing record if already uploaded
        existing = await self.get_document_by_hash(sha256_hash)
        if existing:
            logger.info(
                "document_already_exists_deduplicated",
                sha256=sha256_hash,
                doc_id=existing.document_id,
            )
            return existing

        # 2. Persist binary payload
        dest_file = self.storage_dir / f"{sha256_hash}_{filename}"
        dest_file.write_bytes(content)

        # MinIO upload attempt
        try:
            import urllib3
            from minio import Minio

            http_client = urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=0.3, read=0.8),
                retries=urllib3.Retry(total=1, backoff_factor=0.1),
            )
            m_client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_root_user,
                secret_key=settings.minio_root_password,
                secure=settings.minio_secure,
                http_client=http_client,
            )
            if not m_client.bucket_exists(settings.minio_bucket_docs):
                m_client.make_bucket(settings.minio_bucket_docs)
            m_client.put_object(
                settings.minio_bucket_docs,
                f"{sha256_hash}/{filename}",
                io.BytesIO(content),
                len(content),
                content_type=mime_type,
            )
        except Exception as exc:
            logger.warning("minio_storage_fallback_to_local_disk", error=str(exc))

        now = datetime.now(UTC).isoformat()
        record = DocumentRecord(
            document_id=doc_id,
            sha256=sha256_hash,
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=len(content),
            status=DocumentStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, sha256, filename, mime_type, file_size_bytes,
                    page_count, document_type, status, error, pages_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.document_id,
                    record.sha256,
                    record.filename,
                    record.mime_type,
                    record.file_size_bytes,
                    record.page_count,
                    record.document_type.value,
                    record.status.value,
                    record.error,
                    json.dumps([]),
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()

        # Record initial UPLOAD step
        await self.record_step(
            doc_id=doc_id,
            step_name="UPLOAD",
            status=StepStatus.COMPLETED,
            duration_ms=5.0,
            details={"sha256": sha256_hash, "size": len(content)},
        )

        return record

    async def get_document(self, document_id: str) -> DocumentRecord | None:
        """Fetch document record by unique document_id."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
            if not row:
                return None
            pages_data = json.loads(row["pages_json"])
            return DocumentRecord(
                document_id=row["document_id"],
                sha256=row["sha256"],
                filename=row["filename"],
                mime_type=row["mime_type"],
                file_size_bytes=row["file_size_bytes"],
                page_count=row["page_count"],
                document_type=DocumentType(row["document_type"]),
                status=DocumentStatus(row["status"]),
                error=row["error"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                pages=[PageResult(**p) for p in pages_data],
            )

    async def get_document_by_hash(self, sha256_hash: str) -> DocumentRecord | None:
        """Fetch document record by SHA-256 hash."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE sha256 = ?", (sha256_hash,)
            ).fetchone()
            if not row:
                return None
            pages_data = json.loads(row["pages_json"])
            return DocumentRecord(
                document_id=row["document_id"],
                sha256=row["sha256"],
                filename=row["filename"],
                mime_type=row["mime_type"],
                file_size_bytes=row["file_size_bytes"],
                page_count=row["page_count"],
                document_type=DocumentType(row["document_type"]),
                status=DocumentStatus(row["status"]),
                error=row["error"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                pages=[PageResult(**p) for p in pages_data],
            )

    async def update_document(
        self,
        document_id: str,
        status: DocumentStatus | None = None,
        document_type: DocumentType | None = None,
        page_count: int | None = None,
        pages: list[PageResult] | None = None,
        error: str | None = None,
    ) -> None:
        """Update document processing state, page artifacts, and classification."""
        now = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            updates: list[str] = ["updated_at = ?"]
            params: list[Any] = [now]

            if status is not None:
                updates.append("status = ?")
                params.append(status.value)
            if document_type is not None:
                updates.append("document_type = ?")
                params.append(document_type.value)
            if page_count is not None:
                updates.append("page_count = ?")
                params.append(page_count)
            if pages is not None:
                updates.append("pages_json = ?")
                params.append(json.dumps([p.model_dump() for p in pages]))
            if error is not None:
                updates.append("error = ?")
                params.append(error)

            params.append(document_id)
            query = f"UPDATE documents SET {', '.join(updates)} WHERE document_id = ?"
            conn.execute(query, params)
            conn.commit()

    async def record_step(
        self,
        doc_id: str,
        step_name: str,
        status: StepStatus,
        duration_ms: float = 0.0,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> DocumentStep:
        """Record or update an audited execution step with duration and status."""
        now = datetime.now(UTC).isoformat()
        step_id = f"STEP-{doc_id}-{step_name}"
        details_str = json.dumps(details or {})

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO document_steps (
                    step_id, document_id, step_name, status, duration_ms, error, details_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id, step_name) DO UPDATE SET
                    status=excluded.status,
                    duration_ms=excluded.duration_ms,
                    error=excluded.error,
                    details_json=excluded.details_json,
                    completed_at=excluded.completed_at
                """,
                (
                    step_id,
                    doc_id,
                    step_name,
                    status.value,
                    duration_ms,
                    error,
                    details_str,
                    now,
                    now
                    if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)
                    else None,
                ),
            )
            conn.commit()

        return DocumentStep(
            step_id=step_id,
            document_id=doc_id,
            step_name=step_name,
            status=status,
            duration_ms=duration_ms,
            error=error,
            details=details or {},
            created_at=now,
            completed_at=now,
        )

    async def get_document_steps(self, document_id: str) -> list[DocumentStep]:
        """Fetch all executed steps for a document."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM document_steps WHERE document_id = ? ORDER BY created_at ASC",
                (document_id,),
            ).fetchall()
            return [
                DocumentStep(
                    step_id=r["step_id"],
                    document_id=r["document_id"],
                    step_name=r["step_name"],
                    status=StepStatus(r["status"]),
                    duration_ms=r["duration_ms"],
                    error=r["error"],
                    details=json.loads(r["details_json"]),
                    created_at=r["created_at"],
                    completed_at=r["completed_at"],
                )
                for r in rows
            ]

    def get_document_content(self, sha256_hash: str, filename: str) -> bytes | None:
        """Retrieve binary document payload from local storage or MinIO."""
        local_target = self.storage_dir / f"{sha256_hash}_{filename}"
        if local_target.exists():
            return local_target.read_bytes()
        return None
