"""Async generations API (Sprint 3 refactor).

  POST /generations          → create pending row, enqueue Celery task,
                                return {id, status: "pending"}
  GET  /generations/{id}     → fetch a row (owner-only) — frontend polls
                                this until status is terminal
  GET  /generations          → list current user's generations, newest first

Credit deduction and provider invocation live in the Celery task
(app/tasks/generation.py), not here. This file only does HTTP I/O.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, desc, select

from app.core.db import get_session
from app.deps.auth import CurrentUser
from app.models.generation import Generation, GenerationStatus
from app.providers import GenerationInput, InputType, registry
from app.tasks.generation import run_generation

router = APIRouter()


class CreateGenerationRequest(BaseModel):
    """Request body for POST /generations."""

    model_id: str = Field(..., description="Must match a model returned by GET /models.")
    inputs: GenerationInput


class GenerationResponse(BaseModel):
    """Public-facing shape of a Generation row.

    Mirrors the DB columns we want to expose. Excludes user_id (already
    implicit via auth) and inputs (already in `prompt` for Sprint 3).
    """

    id: UUID
    model_id: str
    prompt: str
    status: GenerationStatus
    result_text: str | None
    result_url: str | None
    error: str | None
    cost_in_credits: int
    created_at: datetime
    updated_at: datetime


def _to_response(row: Generation) -> GenerationResponse:
    return GenerationResponse(
        id=row.id,
        model_id=row.model_id,
        prompt=row.prompt,
        status=row.status,
        result_text=row.result_text,
        result_url=row.result_url,
        error=row.error,
        cost_in_credits=row.cost_in_credits,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/generations",
    response_model=GenerationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["generations"],
)
def create_generation(
    req: CreateGenerationRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> GenerationResponse:
    """Submit a new generation. Returns immediately with status=pending.

    The Celery worker picks up the row, charges credits, runs the provider,
    and lands it in done/failed. Clients poll `GET /generations/{id}` for
    updates.
    """
    try:
        config, _adapter = registry.get(req.model_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    if not config.enabled:
        # Treat disabled models as 404 — the model dropdown shouldn't have
        # offered it in the first place, so a request for it is a stale
        # client or a hand-rolled call.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {req.model_id!r} is not currently available.",
        )

    # Validate inputs against the model's declared input_types.
    if InputType.TEXT in config.input_types and not req.inputs.text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Model {req.model_id!r} requires a 'text' input.",
        )

    row = Generation(
        user_id=user.id,
        model_id=config.id,
        prompt=req.inputs.text or "",
        status=GenerationStatus.PENDING,
        # Snapshot the cost — if registry config changes later, this row's
        # historical cost is preserved.
        cost_in_credits=config.cost_in_credits,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    # Enqueue. .delay returns an AsyncResult we don't need to keep — the
    # generations table is our source of truth for status, not Redis.
    run_generation.delay(str(row.id))

    return _to_response(row)


@router.get(
    "/generations/{generation_id}",
    response_model=GenerationResponse,
    tags=["generations"],
)
def get_generation(
    generation_id: UUID,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> GenerationResponse:
    """Fetch one generation. Returns 404 if it isn't the caller's row."""
    row = session.get(Generation, generation_id)
    if row is None or row.user_id != user.id:
        # Return 404 either way — don't leak whether a foreign generation
        # exists. (Common practice for owner-scoped resources.)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found.",
        )
    return _to_response(row)


@router.get(
    "/generations",
    response_model=list[GenerationResponse],
    tags=["generations"],
)
def list_generations(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[GenerationResponse]:
    """List the caller's generations, newest first."""
    rows = session.exec(
        select(Generation)
        .where(Generation.user_id == user.id)
        .order_by(desc(Generation.created_at))
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_response(row) for row in rows]
