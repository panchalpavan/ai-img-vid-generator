"""FastAPI application entry point.

Run locally with: `uv run uvicorn app.main:app --reload --port 8000`
Or from repo root: `npm run dev:api`
"""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.routers import billing as billing_router
from app.routers import generations as generations_router
from app.routers import me as me_router
from app.routers import models as models_router
from app.routers import references as references_router

app = FastAPI(
    title="img-vid-generation API",
    description="Backend for the img-vid-generation app.",
    version="0.1.0",
)

# Allow the Next.js frontend to call us from a different origin.
# Origins come from CORS_ALLOWED_ORIGINS env (comma-separated). Defaults to
# http://localhost:3000 for dev convenience; deploy must set this to the
# production frontend domain. See app/core/config.py for the parsed list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sub-routers.
app.include_router(me_router.router)
app.include_router(models_router.router)
app.include_router(generations_router.router)
app.include_router(references_router.router)
app.include_router(billing_router.router)

# Type alias so route signatures stay short and reusable.
SessionDep = Annotated[Session, Depends(get_session)]


class HealthResponse(BaseModel):
    """Response shape for /healthz (liveness check)."""

    status: str
    service: str


class DBHealthResponse(BaseModel):
    """Response shape for /healthz/db (readiness check including DB)."""

    status: str
    service: str
    db: str
    probe: int


@app.get("/healthz", response_model=HealthResponse, tags=["meta"])
async def healthz() -> HealthResponse:
    """Liveness probe. Returns OK if the process is running.

    Cheap — does not touch the database. Suitable for load-balancer
    liveness checks that fire every few seconds.
    """
    return HealthResponse(status="ok", service="img-vid-generation-api")


@app.get("/healthz/db", response_model=DBHealthResponse, tags=["meta"])
def healthz_db(session: SessionDep) -> DBHealthResponse:
    """Readiness probe. Verifies the database is reachable by running SELECT 1.

    More expensive than /healthz — actually hits the DB. Use for readiness
    checks that gate traffic, or as a smoke test during deploys.
    """
    probe: int = session.execute(text("SELECT 1")).scalar_one()
    return DBHealthResponse(
        status="ok",
        service="img-vid-generation-api",
        db="reachable",
        probe=probe,
    )
