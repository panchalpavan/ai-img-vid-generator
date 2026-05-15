"""FastAPI application entry point.

Run locally with: `uv run uvicorn app.main:app --reload --port 8000`
Or from repo root: `npm run dev:api`
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="img-vid-generation API",
    description="Backend for the img-vid-generation app.",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    """Response shape for the /healthz endpoint."""

    status: str
    service: str


@app.get("/healthz", response_model=HealthResponse, tags=["meta"])
async def healthz() -> HealthResponse:
    """Liveness probe. Returns a static OK payload.

    Used by:
    - Local dev (sanity check that the server is up)
    - Production load balancers (readiness/liveness checks)
    - CI smoke tests
    """
    return HealthResponse(status="ok", service="img-vid-generation-api")
