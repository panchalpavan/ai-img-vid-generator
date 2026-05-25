"""One-shot script to apply our bucket's CORS policy.

Why this is a separate script and not part of app startup:
  - CORS is a bucket-level setting that almost never changes.
  - Running it on every app boot would be noise; running it on every code
    deploy would be a footgun if someone edits the rule from the dashboard
    and a deploy quietly overwrites it.
  - Keeping it as an explicit script makes the policy change reviewable
    and intentional.

The list of allowed origins is read from `CORS_ALLOWED_ORIGINS` in the
environment — same source of truth as the FastAPI CORSMiddleware. That
keeps "what origins can talk to us" in one place; when you add a
production frontend domain, both the API CORS middleware and the R2
bucket CORS rule pick it up automatically the next time this script
runs.

Run with:
  uv --directory apps/api run python -m scripts.setup_r2_cors

Requires the configured R2 token to have **admin scope** for this bucket
(not just Object R/W). The runtime app only needs Object R/W; admin is
needed solely to mutate bucket-level config like CORS. See GOTCHAS.md.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.storage import configure_cors


def main() -> None:
    origins = settings.cors_allowed_origins_list
    if not origins:
        raise SystemExit(
            "No origins configured. Set CORS_ALLOWED_ORIGINS in apps/api/.env."
        )
    configure_cors(origins)
    print("CORS policy applied.")
    for origin in origins:
        print(f"  - {origin}")


if __name__ == "__main__":
    main()
