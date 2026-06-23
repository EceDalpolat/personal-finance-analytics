"""ai-engine settings, loaded from environment via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Anthropic / Claude ---
    anthropic_api_key: str = "sk-ant-placeholder"
    ai_model_id: str = "claude-sonnet-4-6"     # pinned by CLAUDE.md — do not change without discussion
    ai_max_tokens: int = 2048
    ai_effort: str = "medium"                  # low | medium | high | max
    ai_use_thinking: bool = True               # adaptive thinking on chat calls

    # --- analytics-db (dbt warehouse) ---
    analytics_db_host: str = "analytics-db"
    analytics_db_port: int = 5432
    analytics_db_name: str = "analytics"
    analytics_db_user: str = "analytics"
    analytics_db_password: str = "changeme"

    # --- observability ---
    service_name: str = "ai-engine"
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None

    @property
    def analytics_dsn(self) -> str:
        return (
            f"postgresql://{self.analytics_db_user}:{self.analytics_db_password}"
            f"@{self.analytics_db_host}:{self.analytics_db_port}/{self.analytics_db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
