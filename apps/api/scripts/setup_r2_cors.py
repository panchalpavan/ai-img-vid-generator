"""One-shot script to apply our bucket's CORS policy.

Why this is a separate script and not part of app startup:
  - CORS is a bucket-level setting that almost never changes.
  - Running it on every app boot would be noise; running it on every code
    deploy would be a footgun if someone edits the rule from the dashboard
    and a deploy quietly overwrites it.
  - Keeping it as an explicit script makes the policy change reviewable
    and intentional.

Run with:
  uv --directory apps/api run python scripts/setup_r2_cors.py
"""

from __future__ import annotations

from app.core.storage import configure_cors

# Origins allowed to PUT/GET objects via the browser. Add the production
# domain here when we deploy (Sprint 7).
ALLOWED_ORIGINS = [
    "http://localhost:3000",
]


def main() -> None:
    configure_cors(ALLOWED_ORIGINS)
    print("CORS policy applied.")
    for origin in ALLOWED_ORIGINS:
        print(f"  - {origin}")


if __name__ == "__main__":
    main()
