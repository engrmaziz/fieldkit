"""Immutable Landing Zone with MinIO S3 and local storage support."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

from minio import Minio


class LandingZone:
    """Manages raw immutable landing of enterprise source payloads."""

    def __init__(
        self,
        bucket_name: str = "foundry-landing",
        minio_endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = False,
        local_landing_dir: str | Path = "data/landing",
    ) -> None:
        self.bucket_name = bucket_name
        self.endpoint = minio_endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        self.secure = secure
        self.local_dir = Path(local_landing_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.local_dir / "landing_index.json"

        self._minio_client: Minio | None = None
        self._init_minio()

    def _init_minio(self) -> None:
        try:
            client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            # Ping/check if bucket exists
            if not client.bucket_exists(self.bucket_name):
                client.make_bucket(self.bucket_name)
            self._minio_client = client
        except Exception:
            # Fallback to local landing directory
            self._minio_client = None

    def _load_index(self) -> dict[str, str]:
        if self.index_file.exists():
            try:
                with open(self.index_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_index(self, index: dict[str, str]) -> None:
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    def is_already_landed(self, source: str, raw_bytes: bytes) -> bool:
        """Returns True if this exact payload for this source has already been landed."""
        if not raw_bytes:
            return False
        sha = hashlib.sha256(raw_bytes).hexdigest()
        index = self._load_index()
        key = f"{source}:{sha}"
        return key in index

    def land(
        self,
        source: str,
        run_id: str,
        filename: str,
        raw_bytes: bytes,
    ) -> tuple[str, str, bool]:
        """Lands raw bytes immutably. Returns (object_key, sha256, skipped)."""
        if not raw_bytes:
            return "", "", False

        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        index = self._load_index()
        index_key = f"{source}:{sha256}"

        if index_key in index:
            # Idempotent skip: payload already landed in a prior run
            return index[index_key], sha256, True

        object_key = f"landing/{source}/{run_id}/{filename}"

        # 1. Write to MinIO if available
        if self._minio_client:
            try:
                self._minio_client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=object_key,
                    data=io.BytesIO(raw_bytes),
                    length=len(raw_bytes),
                    metadata={"sha256": sha256, "source": source, "run_id": run_id},
                )
            except Exception as e:
                print(f"Warning: MinIO landing failed, using local disk fallback: {e}")
                self._land_local(object_key, raw_bytes)
        else:
            self._land_local(object_key, raw_bytes)

        # 2. Update index
        index[index_key] = object_key
        self._save_index(index)
        return object_key, sha256, False

    def _land_local(self, object_key: str, raw_bytes: bytes) -> None:
        target_path = self.local_dir / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(raw_bytes)
