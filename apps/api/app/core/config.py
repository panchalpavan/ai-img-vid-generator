"""Application settings loaded from environment variables.

All config lives here. Anything elsewhere that wants to read an env var should
import `settings` from this module — never read `os.environ` directly.

Pydantic Settings validates types at startup: if DATABASE_URL is malformed or
missing, the app fails fast with a clear error rather than crashing later.
"""

from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are loaded from (in order of precedence):
    1. Environment variables
    2. `.env` file in this directory
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database — Supabase free Postgres (dev) or Cloud SQL (prod). Validated as URL.
    database_url: PostgresDsn


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor.

    Using lru_cache means Settings() is instantiated once per process, even
    if called from many places. Important because BaseSettings reads the .env
    file on construction.
    """
    return Settings()


settings = get_settings()
