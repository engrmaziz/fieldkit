"""Shared application settings using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Common settings across all Fieldkit services."""

    environment: str = "development"
    service_name: str = "fieldkit-service"
    log_level: str = "INFO"

    # Tracing
    otel_exporter_otlp_endpoint: str | None = None

    # Keycloak / Auth
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "halden"
    keycloak_client_id: str = "api"
    keycloak_jwks_url: str = "http://localhost:8080/realms/halden/protocol/openid-connect/certs"

    # LLM & Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_default: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = 60

    # Tracehub (Project 7)
    tracehub_url: str = "http://localhost:8006"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_common_settings() -> CommonSettings:
    """Return cached common settings."""
    return CommonSettings()
