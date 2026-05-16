"""POST /generations — synchronous generation endpoint (Sprint 2 POC).

Sprint 3 will refactor this to enqueue a Celery task and return a
`pending` row, with status polled at `GET /generations/{id}`. That refactor
also adds credit deduction tied to the new `generations` table row. For
now this just calls the adapter directly and returns the result.

Auth: requires a valid JWT. The current user is provisioned just-in-time
(see app/deps/auth.py) if this is their first authenticated call.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps.auth import CurrentUser
from app.providers import (
    GenerationInput,
    GenerationOutput,
    InputType,
    registry,
)

router = APIRouter()


class CreateGenerationRequest(BaseModel):
    """Request body for POST /generations."""

    model_id: str = Field(..., description="Must match a model returned by GET /models.")
    inputs: GenerationInput


@router.post(
    "/generations",
    response_model=GenerationOutput,
    tags=["generations"],
)
def create_generation(
    req: CreateGenerationRequest,
    # Even though this user isn't (yet) consumed below, requiring auth
    # provisions them and rejects unauthenticated callers. Keep the
    # parameter so the dependency runs.
    _user: CurrentUser,
) -> GenerationOutput:
    """Run a generation synchronously against the selected model."""
    try:
        config, adapter = registry.get(req.model_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    # Input-shape validation: every input_type the model requires must
    # have a non-empty value supplied. (We assume required-for-now; later
    # we can add per-input optionality if needed.)
    if InputType.TEXT in config.input_types and not req.inputs.text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Model {req.model_id!r} requires a 'text' input.",
        )

    # TODO (Sprint 3): credit deduction. Once `generations` table exists
    # we'll insert a row, use its UUID as the CreditTransaction.reference_id,
    # debit profiles.credit_balance, all in one transaction. Dev user (per
    # settings.dev_email) bypasses the debit.

    try:
        return adapter.generate(req.model_id, req.inputs)
    except RuntimeError as exc:
        # Misconfiguration (e.g., missing API key) — surface as 500 with the
        # provider's message so the dev can fix it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Provider call failed (network, rate limit, content blocked, etc.).
        # 502 because it's an upstream-service failure.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Provider error: {exc}",
        ) from exc
