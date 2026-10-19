"""Configuration settings for Tracehub service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TracehubSettings(BaseSettings):
    """Runtime settings for Tracehub."""

    service_name: str = "tracehub"
    environment: str = "development"
    port: int = 8006

    # ClickHouse Analytics Storage
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "fieldkit_tracehub"

    # Redpanda / Kafka Telemetry Queue
    kafka_brokers: str = "localhost:19092"
    kafka_spans_topic: str = "otel.spans"

    # OpenTelemetry
    otel_exporter_endpoint: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="TRACEHUB_",
        case_sensitive=False,
        extra="ignore",
    )


settings = TracehubSettings()
