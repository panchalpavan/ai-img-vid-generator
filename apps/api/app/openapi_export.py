"""Dump the FastAPI app's OpenAPI schema to stdout as JSON.

Used by the root-level `gen:api-types` script to produce input for
`openapi-typescript`. Calling `app.openapi()` directly avoids spinning
up a real HTTP server just to fetch /openapi.json.

Usage (from `apps/api/`):
    uv run python -m app.openapi_export > ../../packages/shared-types/openapi.json
"""

import json
import sys

from app.main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
