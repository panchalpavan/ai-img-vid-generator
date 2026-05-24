"""Celery tasks that drive a Generation row to a terminal state.

Two tasks, dispatched by ModelConfig.is_async:

  run_generation(generation_id)
    Entry point — Celery picks this up after POST /generations enqueues it.
    Loads the row, charges credits, then either:
      - Sync provider:  calls adapter.generate(), persists, marks DONE/FAILED.
      - Async provider: calls adapter.submit_async(), stores provider job id,
                        enqueues poll_generation, returns immediately.

  poll_generation(generation_id)
    Only used for async providers. Calls adapter.poll_status(); on DONE
    persists and marks the row DONE, on FAILED refunds + marks FAILED, on
    PROCESSING **re-enqueues itself** with a delay so the worker slot is
    free between polls. Aborts with a timeout failure if the job runs
    longer than _MAX_POLL_DURATION_SECONDS.

Both tasks are idempotent — a row already at DONE/FAILED is a no-op,
which makes Celery retries and accidental re-enqueues safe.

Credit handling (ADR-0006):
  - Dev user (DEV_EMAIL) bypasses charging.
  - Others: SELECT FOR UPDATE on `profiles`, debit, insert
    CreditTransaction(type=GENERATION, reference_id=generation.id).
  - On any post-charge failure (sync error, async timeout, async FAILED):
    insert CreditTransaction(type=REFUND, same reference_id), re-credit
    profile balance.
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
from app.providers import (
    AsyncProviderAdapter,
    GenerationInput,
    GenerationOutput,
    JobState,
    OutputType,
    SyncProviderAdapter,
    registry,
)
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

# How often poll_generation re-checks an in-flight async job. 3s balances
# UI responsiveness (the frontend polls /generations/{id} at 1s) against
# upstream rate limits.
_POLL_INTERVAL_SECONDS = 3

# Hard ceiling on how long any single async job is allowed to take. Beyond
# this we mark the row FAILED with a timeout and refund. Currently scoped
# to image generation; videos in Sjinn (future) will need a higher value
# or a per-model override.
_MAX_POLL_DURATION_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Entry-point task
# ---------------------------------------------------------------------------


@celery_app.task(name="app.tasks.run_generation")
def run_generation(generation_id: str) -> None:
    """Process the Generation row identified by `generation_id`.

    For sync providers this does the whole flow end-to-end. For async
    providers it submits the job and enqueues poll_generation; the rest
    of the lifecycle is driven by that second task.
    """
    gen_uuid = UUID(generation_id)
    with Session(engine) as session:
        generation = session.get(Generation, gen_uuid)
        if generation is None:
            # Row was deleted between enqueue and pickup — nothing to do.
            return
        if generation.status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            return

        _set_status(session, generation, GenerationStatus.PROCESSING)

        user = session.get(User, generation.user_id)
        if user is None:
            _fail(session, generation, "Owning user no longer exists.")
            return

        dev_bypass = _is_dev_user(user)
        if not dev_bypass and not _charge_credits(session, user.id, generation):
            _fail(session, generation, "Insufficient credits.")
            return

        try:
            config, adapter = registry.get(generation.model_id)
        except KeyError as exc:
            _refund_if_charged(session, user, generation)
            _fail(session, generation, f"Unknown model: {exc}")
            return

        inputs = GenerationInput(
            text=generation.prompt,
            image_urls=[],  # TODO(sprint-4A.5+): plumb staged refs through the row
        )

        if config.is_async:
            _dispatch_async(session, generation, adapter, inputs)
        else:
            _dispatch_sync(session, generation, adapter, inputs)


# ---------------------------------------------------------------------------
# Poll task — only used for async providers
# ---------------------------------------------------------------------------


@celery_app.task(name="app.tasks.poll_generation")
def poll_generation(generation_id: str) -> None:
    """Check an in-flight async job; re-enqueue or finalize the row.

    Designed to be cheap and bounded: one HTTP call to the provider, then
    either flip the row to terminal state or schedule another poll. Worker
    slot is held only for the duration of one poll, not the whole job.
    """
    gen_uuid = UUID(generation_id)
    with Session(engine) as session:
        generation = session.get(Generation, gen_uuid)
        if generation is None:
            return
        if generation.status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            return
        if not generation.provider_job_id:
            # Should never happen — run_generation always sets this before
            # enqueueing the poll. Defensive: don't loop forever.
            _fail(session, generation, "Internal: poll task fired without a job id.")
            return

        # Overall timeout. We measure from row creation rather than from
        # first poll attempt because that's a strictly-bounded, monotonic
        # reference even across worker restarts.
        elapsed = (datetime.now(UTC) - _aware(generation.created_at)).total_seconds()
        if elapsed > _MAX_POLL_DURATION_SECONDS:
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(
                session,
                generation,
                f"Job exceeded {_MAX_POLL_DURATION_SECONDS}s timeout (provider {generation.model_id!r}).",
            )
            return

        try:
            _config, adapter = registry.get(generation.model_id)
        except KeyError as exc:
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(session, generation, f"Unknown model: {exc}")
            return

        if not isinstance(adapter, AsyncProviderAdapter):
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(
                session,
                generation,
                f"Adapter for {generation.model_id!r} is not async; can't poll.",
            )
            return

        try:
            status = adapter.poll_status(
                generation.model_id, generation.provider_job_id
            )
        except Exception as exc:  # noqa: BLE001
            # Transient query failures: re-enqueue rather than fail the
            # generation, but cap retries via the elapsed-time check above.
            # The next poll attempt will hit the same code path.
            poll_generation.apply_async(
                args=[generation_id], countdown=_POLL_INTERVAL_SECONDS
            )
            del exc
            return

        if status.state is JobState.PROCESSING:
            poll_generation.apply_async(
                args=[generation_id], countdown=_POLL_INTERVAL_SECONDS
            )
            return

        if status.state is JobState.FAILED:
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(session, generation, (status.error or "Provider reported failure.")[:2000])
            return

        # JobState.DONE — finalize with the output
        if status.output is None:
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(session, generation, "Provider reported DONE but returned no output.")
            return

        _finalize_done(session, generation, status.output)


# ---------------------------------------------------------------------------
# Dispatch helpers — one per execution model
# ---------------------------------------------------------------------------


def _dispatch_sync(
    session: Session,
    generation: Generation,
    adapter: object,
    inputs: GenerationInput,
) -> None:
    """Run the entire generation in this worker invocation (sync path)."""
    if not isinstance(adapter, SyncProviderAdapter):
        user = session.get(User, generation.user_id)
        if user is not None:
            _refund_if_charged(session, user, generation)
        _fail(
            session,
            generation,
            f"Model {generation.model_id!r} is marked sync but its adapter "
            "doesn't implement `generate`.",
        )
        return

    try:
        output = adapter.generate(generation.model_id, inputs)
    except Exception as exc:  # noqa: BLE001 — provider exceptions vary widely
        user = session.get(User, generation.user_id)
        if user is not None:
            _refund_if_charged(session, user, generation)
        _fail(session, generation, f"Provider error: {exc}"[:2000])
        return

    _finalize_done(session, generation, output)


def _dispatch_async(
    session: Session,
    generation: Generation,
    adapter: object,
    inputs: GenerationInput,
) -> None:
    """Submit the job, store its id on the row, enqueue the first poll."""
    if not isinstance(adapter, AsyncProviderAdapter):
        user = session.get(User, generation.user_id)
        if user is not None:
            _refund_if_charged(session, user, generation)
        _fail(
            session,
            generation,
            f"Model {generation.model_id!r} is marked async but its adapter "
            "doesn't implement `submit_async`/`poll_status`.",
        )
        return

    try:
        job_id = adapter.submit_async(generation.model_id, inputs)
    except Exception as exc:  # noqa: BLE001
        user = session.get(User, generation.user_id)
        if user is not None:
            _refund_if_charged(session, user, generation)
        _fail(session, generation, f"Provider submission failed: {exc}"[:2000])
        return

    generation.provider_job_id = job_id
    generation.updated_at = datetime.now(UTC)
    session.add(generation)
    session.commit()

    # Schedule the first poll. apply_async + countdown re-queues this same
    # task with a delay — worker is free to handle other jobs in the
    # meantime.
    poll_generation.apply_async(
        args=[str(generation.id)], countdown=_POLL_INTERVAL_SECONDS
    )


# ---------------------------------------------------------------------------
# Finalize — used by both sync (after generate) and async (after DONE poll)
# ---------------------------------------------------------------------------


def _finalize_done(
    session: Session, generation: Generation, output: GenerationOutput
) -> None:
    """Persist a successful output and mark the row DONE.

    Image outputs are uploaded to R2 first (so the URL we store is durable
    and provider-independent). Storage failures refund + mark FAILED — the
    refund-on-storage-failure policy is flagged in docs/SPRINTS.md as an
    open business-logic question.
    """
    persisted_url = output.url
    if output.output_type == OutputType.IMAGE and output.url is not None:
        try:
            persisted_url = _persist_image_to_r2(generation.id, output)
        except Exception as exc:  # noqa: BLE001 — surface any storage failure
            user = session.get(User, generation.user_id)
            if user is not None:
                _refund_if_charged(session, user, generation)
            _fail(session, generation, f"Storage error: {exc}"[:2000])
            return

    generation.status = GenerationStatus.DONE
    generation.result_text = output.text
    generation.result_url = persisted_url
    generation.updated_at = datetime.now(UTC)
    session.add(generation)
    session.commit()


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
# Row + ledger helpers
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


def _is_dev_user(user: User) -> bool:
    return bool(settings.dev_email and user.email == settings.dev_email)


def _refund_if_charged(
    session: Session, user: User, generation: Generation
) -> None:
    """No-op for dev users; refunds for everyone else."""
    if _is_dev_user(user):
        return
    _refund_credits(session, user.id, generation)


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
    """Reverse a prior debit when the provider fails after we've charged.

    The unique constraint on credit_transactions(type, reference_id) means
    a second refund attempt for the same generation is a no-op at the DB
    layer — important because both timeout paths and explicit-failure paths
    can hit this for the same row in rare cases.
    """
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


def _aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC.

    SQLModel deserializes our timestamp columns as naive datetimes (because
    we store without tz info), but `datetime.now(UTC)` is aware. Subtracting
    them would raise; this helper makes naive ones aware for arithmetic.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
