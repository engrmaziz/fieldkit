"""Application settings for Assistant API service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSISTANT_", extra="ignore")

    app_name: str = "fieldkit-assistant-api"
    port: int = 8002
    host: str = "0.0.0.0"
    database_url: str = "postgresql+asyncpg://fieldkit:fieldkit@localhost:5432/fieldkit"
    ollama_base_url: str = "http://localhost:11434"
    corpus_dir: str = "data/raw/corpus"
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "halden"


settings = Settings()
