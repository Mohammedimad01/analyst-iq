"""Environment-based settings. Values come from the process environment or the repo-root `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
SQLITE_FALLBACK_URL = f"sqlite:///{(BACKEND_DIR / 'analyst_iq.db').as_posix()}"


def normalise_url(value: str) -> str:
    """Neon hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named."""
    value = value.strip()
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix):]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    # Shown in the UI. Single-organisation deployment: see docs/ARCHITECTURE.md ("Security posture").
    organization_name: str = "Demo Retail Co"
    # Public demo deployments: reject data uploads (data is loaded with the CLI instead).
    read_only_mode: bool = False
    # Interactive /docs. Default: on in development, off when ENVIRONMENT=production.
    expose_api_docs: bool | None = None
    log_level: str = "INFO"
    database_url: str = ""
    # Optional direct (non-pooled) URL used only for migrations; Neon's pooled URL is fine for the app itself.
    database_url_direct: str = ""
    # Throwaway database for `pytest --postgres`. Tests drop and recreate every table in it.
    test_database_url: str = ""
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 10
    max_import_rows: int = 200_000
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_timeout_seconds: float = 30.0
    # Shared secret for /api/v1/automation/* (n8n). Empty = automation endpoints are disabled.
    automation_api_key: str = ""
    # Cost guards, counted from stored insights so they survive restarts. A question uses up to two model calls.
    ai_max_requests_per_minute: int = 5
    ai_max_requests_per_day: int = 100

    @field_validator("database_url")
    @classmethod
    def normalise_database_url(cls, value: str) -> str:
        return normalise_url(value) or SQLITE_FALLBACK_URL

    @field_validator("database_url_direct", "test_database_url")
    @classmethod
    def normalise_optional_url(cls, value: str) -> str:
        return normalise_url(value)

    @property
    def migration_database_url(self) -> str:
        return self.database_url_direct or self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_backend(self) -> str:
        return "sqlite" if self.database_url.startswith("sqlite") else "postgresql"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
