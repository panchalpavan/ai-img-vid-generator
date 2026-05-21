"""Application settings loaded from environment variables.

All config lives here. Anything elsewhere that wants to read an env var should
import `settings` from this module — never read `os.environ` directly.

Pydantic Settings validates types at startup: if DATABASE_URL is malformed or
missing, the app fails fast with a clear error rather than crashing later.
"""

from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
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

    # Redis — Celery broker + result backend. Local Docker on port 6380 (host 6379
    # is taken by another project on this machine). Validated as redis:// URL.
    redis_url: RedisDsn

    # JWT — shared secret with apps/web (ADR-0009). HS256 algorithm. Auth.js
    # signs session tokens with this key; FastAPI verifies them.
    jwt_secret: str

    # Dev convenience: if a signed-in user's email matches this, the /me
    # response shows an effectively-infinite balance. Leave unset in
    # production. Optional — when None, no user gets the bypass.
    dev_email: str | None = None

    # New users start with this credit balance. Default 0 (cold start UX),
    # set to e.g. 5 to give every signup five free generations. Insert is
    # logged as a CreditTransaction(type=STARTER_BONUS) for audit.
    free_starter_credits: int = 0

    # Google AI Studio API key — used by the Gemini provider adapter
    # (apps/api/app/providers/google_ai_studio.py). Get one for free at
    # https://aistudio.google.com/apikey. Sprint 7 migrates to Vertex AI
    # which uses GCP IAM instead.
    google_api_key: str | None = None

    # Seegen.ai API key — used by the Seegen provider adapter
    # (apps/api/app/providers/seegen.py). Token format `zimg_...`.
    # Get one at https://seegen.ai (free tier: 200 credits at signup).
    seegen_api_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor.

    Using lru_cache means Settings() is instantiated once per process, even
    if called from many places. Important because BaseSettings reads the .env
    file on construction.
    """
    return Settings()


settings = get_settings()
