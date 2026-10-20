"""Configuration settings for Fieldkit DocAI service."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class DocAISettings(BaseSettings):
    """Configuration for DocAI service, MinIO storage, Redis job queue, and OCR."""

    environment: str = "development"
    port: int = 8004
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Storage & DB
    database_url: str = os.getenv("DOCAI_DATABASE_URL", "sqlite:///./data/docai.db")
    storage_dir: str = os.getenv("DOCAI_STORAGE_DIR", "./data/docai_storage")

    # MinIO
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_root_user: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_root_password: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    minio_bucket_docs: str = os.getenv("MINIO_BUCKET_DOCS", "docs")

    # Redis / arq
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Preprocessing & OCR
    dpi: int = 200
    skip_deskew_angle_deg: float = 0.3
    poppler_path: str | None = os.getenv("POPPLER_PATH", None)
    tesseract_cmd: str | None = os.getenv("TESSERACT_CMD", None)

    model_config = SettingsConfigDict(
        env_prefix="DOCAI_",
        env_file=".env",
        extra="ignore",
    )


settings = DocAISettings()
