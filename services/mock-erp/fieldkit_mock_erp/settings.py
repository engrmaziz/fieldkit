"""Configuration settings for Mock ERP service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class MockERPSettings(BaseSettings):
    """Mock ERP configuration settings."""

    app_name: str = "mock-erp"
    host: str = "0.0.0.0"
    port: int = 8007
    failure_rate_503: float = 0.03  # 3% simulated transient 503s

    model_config = SettingsConfigDict(env_prefix="MOCK_ERP_", extra="ignore")


settings = MockERPSettings()
