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

import base64
import urllib.request
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.storage import upload_bytes
from app.models.credit_transaction import CreditTransaction, TransactionType
from app.models.generation import Generation, GenerationStatus
from app.models.profile import Profile
from app.models.user import User
from app.providers import GenerationInput, GenerationOutput, OutputType, registry
from app.tasks import celery_app

# Browser-like UA so server-side fetches don't get 403'd by Cloudflare's bot
# detection. Same workaround as the Pollinations adapter and the r2.dev
# gotcha — documented in docs/GOTCHAS.md.
_FETCH_USER_AGENT = (
    "Mozilla/5.0 (img-vid-generation worker) AppleWebKit/537.36 (KHTML, like Gecko)"
)
_FETCH_TIMEOUT_SECONDS = 60

# Subset of image MIME types we know how to map to file extensions. If a
# provider returns something exotic we fall back to `.bin` rather than guess.
_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


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

        # ---- Persist image outputs to our R2 ----------------------------
        # Text outputs are written to result_text and need no storage step.
        # Image outputs come back from any adapter in one of two shapes:
        #   1. data:<mime>;base64,...   — bytes embedded inline
        #   2. https://...              — URL on some other host
        # (e.g. today Pollinations happens to emit shape #1, Seegen emits
        # shape #2 — those are just examples of the current registry, not
        # a contract; the branching below is by URL shape, not provider.)
        #
        # We move the bytes to our R2 bucket in either case so the result is
        # durable, has a stable URL we control, and isn't dependent on the
        # provider keeping the original around.
        persisted_url = output.url
        if output.output_type == OutputType.IMAGE and output.url is not None:
            try:
                persisted_url = _persist_image_to_r2(generation.id, output)
            except Exception as exc:  # noqa: BLE001 — surface any storage failure
                if not dev_bypass:
                    _refund_credits(session, user.id, generation)
                _fail(session, generation, f"Storage error: {exc}"[:2000])
                return

        # ---- Success — store result -------------------------------------
        generation.status = GenerationStatus.DONE
        generation.result_text = output.text
        generation.result_url = persisted_url
        generation.updated_at = datetime.now(UTC)
        session.add(generation)
        session.commit()
        # Reference to config kept for symmetry with future per-model
        # post-processing; unused for now.
        _ = config


def _persist_image_to_r2(generation_id: UUID, output: GenerationOutput) -> str:
    """Move an image result from the provider into our R2 bucket.

    Returns the public R2 URL. Raises if the source can't be read or the
    upload fails — caller catches and converts to a FAILED row with refund.
    """
    if output.url is None:
        raise ValueError("Image output has no URL to persist.")

    if output.url.startswith("data:"):
        data, mime = _decode_data_uri(output.url)
    else:
        data, mime = _fetch_remote_bytes(output.url)

    ext = _MIME_TO_EXT.get(mime, "bin")
    key = f"generations/{generation_id}.{ext}"
    return upload_bytes(key, data, content_type=mime)


def _decode_data_uri(uri: str) -> tuple[bytes, str]:
    """Decode a `data:<mime>;base64,<payload>` URI into (bytes, mime).

    Provider-agnostic — works for any adapter that returns base64 data URIs.
    (Example: as of writing, Pollinations is the one adapter that does so.)

    Plain (non-base64) data URIs are technically valid per RFC 2397 but
    rejected here; raise if encountered so we notice the new shape rather
    than silently corrupt a result.
    """
    header, _, payload = uri.partition(",")
    if not payload or ";base64" not in header:
        raise ValueError(f"Unsupported data URI shape: {header[:60]}...")
    # header looks like `data:image/png;base64`; the slice between `data:`
    # and the first `;` is the MIME type.
    mime = header[len("data:") :].split(";", 1)[0] or "application/octet-stream"
    return base64.b64decode(payload), mime


def _fetch_remote_bytes(url: str) -> tuple[bytes, str]:
    """Server-side GET for image bytes. Returns (data, mime)."""
    request = urllib.request.Request(url, headers={"User-Agent": _FETCH_USER_AGENT})
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as resp:  # noqa: S310
        data: bytes = resp.read()
        mime = resp.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()
    if not data:
        raise RuntimeError(f"Empty response when fetching {url}")
    return data, mime


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
