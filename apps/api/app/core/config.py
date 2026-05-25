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

    # Cloudflare Workers AI — same Cloudflare account that owns the R2
    # bucket, separate API token (scoped to "Workers AI: Read"). Free tier
    # is roughly 25-100 images/day depending on the model's neuron cost.
    # Both must be set together; missing-config means the adapter doesn't
    # register and the model doesn't appear in /models.
    cloudflare_account_id: str | None = None
    cloudflare_workers_ai_token: str | None = None

    # Cloudflare R2 object storage (Sprint 4A). S3-compatible — boto3 against
    # the R2 endpoint works the same as against S3. Zero egress fees + 10 GB
    # free tier; the only difference from S3 is the regional endpoint URL.
    # All five must be set together; missing-key handling lives in the storage
    # module so the app can boot without R2 configured (during local dev work
    # that doesn't touch storage).
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_endpoint: str | None = None  # https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    r2_bucket: str | None = None
    # Public read URL for browser <img src="..."> — the bucket-specific
    # r2.dev subdomain we enable in the dashboard. Without this, uploaded
    # objects exist but can't be displayed directly in the browser.
    r2_public_url: str | None = None

    # Stripe — credit pack purchases (Sprint 5). All test-mode in dev.
    # The secret key signs API calls server-side; the publishable key is
    # safe to expose to the browser (used if we ever switch to embedded
    # Stripe Elements — hosted Checkout doesn't strictly need it).
    # The webhook secret is per-environment: locally it's whatever the
    # `stripe listen` CLI prints; in prod it's set per webhook endpoint
    # in the Stripe dashboard.
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Price IDs for the three credit packs. The "what credits each pack
    # grants" mapping lives in `app/billing/packs.py` (not here), keyed by
    # these IDs — keeps Stripe's source-of-truth (price_id) separate from
    # our domain-level catalog.
    stripe_price_id_starter: str | None = None
    stripe_price_id_pro: str | None = None
    stripe_price_id_studio: str | None = None
    # Where Stripe should send the browser back after Checkout. Set this
    # to the deployed frontend URL in prod. Two paths are appended by the
    # billing router: ?checkout=success and ?checkout=cancel.
    checkout_return_url_base: str = "http://localhost:3000"

    # Comma-separated list of origins allowed by FastAPI's CORS middleware.
    # Each entry is a fully-qualified origin (scheme + host + port). In
    # dev a single localhost origin is enough; production needs the
    # deployed frontend domain (and optionally a staging one). Trailing
    # slashes are NOT allowed by the CORS spec — keep them off.
    #
    # Example prod value:
    #   CORS_ALLOWED_ORIGINS=https://img-vid-generation.example.com,https://staging.example.com
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Parse the comma-separated env into a list, stripping whitespace.

        Pydantic Settings can't natively read a list from a string env var
        without a custom validator; doing the split lazily via a property
        keeps the env contract simple ("comma-separated string") while
        downstream code gets a real list.
        """
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor.

    Using lru_cache means Settings() is instantiated once per process, even
    if called from many places. Important because BaseSettings reads the .env
    file on construction.
    """
    return Settings()


settings = get_settings()
