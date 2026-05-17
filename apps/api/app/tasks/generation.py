"""Celery task that processes a Generation row to a terminal state.

Lifecycle:
  PENDING (created by POST /generations)
    │
    ▼ task picked up
  PROCESSING (status flipped before provider call)
    │
    ├─► provider succeeds ──► DONE (result stored)
    │
    └─► provider raises ────► FAILED (error stored; credits refunded if charged)

Credit handling (ADR-0006):
  - Dev user (DEV_EMAIL) bypasses charging entirely.
  - Others: SELECT FOR UPDATE on `profiles`, debit if balance sufficient,
    insert CreditTransaction(type=GENERATION, reference_id=generation.id).
  - On provider failure: insert CreditTransaction(type=REFUND, same reference_id),
    re-credit profile balance.

Idempotency: if the row is already in a terminal state when the task fires,
no-op. Safe against accidental re-enqueue or worker retries.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.credit_transaction import CreditTransaction, TransactionType
from app.models.generation import Generation, GenerationStatus
from app.models.profile import Profile
from app.models.user import User
from app.providers import GenerationInput, registry
from app.tasks import celery_app


@celery_app.task(name="app.tasks.run_generation")
def run_generation(generation_id: str) -> None:
    """Process the Generation row identified by `generation_id`."""
    gen_uuid = UUID(generation_id)
    with Session(engine) as session:
        generation = session.get(Generation, gen_uuid)
        if generation is None:
            # Row was deleted between enqueue and pickup — nothing to do.
            return

        # Idempotency guard.
        if generation.status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            return

        # Flip to PROCESSING so the frontend can show "running" instead of
        # "queued" while we wait on the provider.
        _set_status(session, generation, GenerationStatus.PROCESSING)

        user = session.get(User, generation.user_id)
        if user is None:
            _fail(session, generation, "Owning user no longer exists.")
            return

        dev_bypass = bool(settings.dev_email and user.email == settings.dev_email)

        # ---- Charge credits (skipped for dev user) -----------------------
        if not dev_bypass:
            charged = _charge_credits(session, user.id, generation)
            if not charged:
                _fail(session, generation, "Insufficient credits.")
                return

        # ---- Call the provider ------------------------------------------
        try:
            config, adapter = registry.get(generation.model_id)
        except KeyError as exc:
            if not dev_bypass:
                _refund_credits(session, user.id, generation)
            _fail(session, generation, f"Unknown model: {exc}")
            return

        try:
            output = adapter.generate(
                generation.model_id,
                GenerationInput(text=generation.prompt),
            )
        except Exception as exc:  # noqa: BLE001 — provider exceptions vary widely
            if not dev_bypass:
                _refund_credits(session, user.id, generation)
            # Cap error length to schema limit; full traceback stays in logs.
            _fail(session, generation, f"Provider error: {exc}"[:2000])
            return

        # ---- Success — store result -------------------------------------
        generation.status = GenerationStatus.DONE
        generation.result_text = output.text
        generation.result_url = output.url
        generation.updated_at = datetime.now(UTC)
        session.add(generation)
        session.commit()
        # Reference to config kept for symmetry with future per-model
        # post-processing; unused for now.
        _ = config


# ---------------------------------------------------------------------------
# Helpers — keep transactional details out of the main flow
# ---------------------------------------------------------------------------


def _set_status(
    session: Session, generation: Generation, status: GenerationStatus
) -> None:
    generation.status = status
    generation.updated_at = datetime.now(UTC)
    session.add(generation)
    session.commit()
    session.refresh(generation)


def _fail(session: Session, generation: Generation, error: str) -> None:
    generation.status = GenerationStatus.FAILED
    generation.error = error[:2048]
    generation.updated_at = datetime.now(UTC)
    session.add(generation)
    session.commit()


def _charge_credits(session: Session, user_id: UUID, generation: Generation) -> bool:
    """Atomic debit of `cost_in_credits`. Returns False if insufficient.

    Uses SELECT FOR UPDATE so two concurrent workers can't double-spend the
    same balance.
    """
    profile = session.exec(
        select(Profile).where(Profile.user_id == user_id).with_for_update()
    ).first()
    if profile is None or profile.credit_balance < generation.cost_in_credits:
        return False
    session.add(
        CreditTransaction(
            user_id=user_id,
            amount=-generation.cost_in_credits,
            type=TransactionType.GENERATION,
            reference_id=str(generation.id),
        )
    )
    profile.credit_balance -= generation.cost_in_credits
    profile.updated_at = datetime.now(UTC)
    session.add(profile)
    session.commit()
    return True


def _refund_credits(session: Session, user_id: UUID, generation: Generation) -> None:
    """Reverse a prior debit when the provider fails after we've charged."""
    profile = session.exec(
        select(Profile).where(Profile.user_id == user_id).with_for_update()
    ).first()
    if profile is None:
        return
    session.add(
        CreditTransaction(
            user_id=user_id,
            amount=generation.cost_in_credits,
            type=TransactionType.REFUND,
            reference_id=str(generation.id),
        )
    )
    profile.credit_balance += generation.cost_in_credits
    profile.updated_at = datetime.now(UTC)
    session.add(profile)
    session.commit()
