"""Environment-based settings. Values come from the process environment or the repo-root `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
SQLITE_FALLBACK_URL = f"sqlite:///{(BACKEND_DIR / 'analyst_iq.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = ""
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 10
    max_import_rows: int = 200_000
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_timeout_seconds: float = 30.0
    # Cost guards, counted from stored insights so they survive restarts. A question uses up to two model calls.
    ai_max_requests_per_minute: int = 5
    ai_max_requests_per_day: int = 100

    @field_validator("database_url")
    @classmethod
    def normalise_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return SQLITE_FALLBACK_URL
        # Neon hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

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
