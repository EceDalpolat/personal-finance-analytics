"""api settings, loaded from environment via pydantic-settings.

api is the public-facing service: it reads finance marts, proxies chat to
ai-engine (never calls Claude directly — see CLAUDE.md), and mints per-user
Superset guest tokens."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- ai-engine proxy (api never talks to Claude itself) ---
    ai_engine_url: str = "http://ai-engine:8000"
    ai_engine_timeout_seconds: float = 30.0

    # --- Superset (guest-token minting for embedded dashboards) ---
    superset_url: str = "http://superset:8088"
    superset_admin_user: str = "admin"
    superset_admin_password: str = "admin"
    superset_guest_username: str = "embed-guest"

    # --- analytics-db (read-only mart access) ---
    analytics_db_host: str = "analytics-db"
    analytics_db_port: int = 5432
    analytics_db_name: str = "analytics"
    analytics_db_user: str = "analytics"
    analytics_db_password: str = "changeme"

    # --- observability ---
    service_name: str = "api"
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
