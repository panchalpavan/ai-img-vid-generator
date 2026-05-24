"""Billing API — credit pack purchases via Stripe (Sprint 5).

Three endpoints:

  - GET /billing/packs
      Public list of available credit packs (id, credits, price, currency,
      display name). The frontend renders the Buy Credits modal from this.

  - POST /billing/checkout
      Auth'd. Body: {pack_id}. Creates a Stripe Checkout Session for that
      pack and returns the hosted-page URL. The browser then navigates
      to that URL; Stripe handles all card collection and 3DS.

  - POST /webhooks/stripe
      Public (Stripe calls it). Verifies the signature, processes the
      `checkout.session.completed` event, grants credits via a single
      CreditTransaction insert (atomic, idempotent via the
      (type, reference_id) unique constraint).

Idempotency lives in the database, not in this file. The unique constraint
on credit_transactions(type, reference_id) makes a duplicate webhook a
no-op: Postgres raises IntegrityError on the second insert; we catch it
and return 200 so Stripe stops retrying.

Webhook signature verification uses the **raw request body** (bytes), not
the parsed JSON. FastAPI's automatic JSON parsing would re-serialize and
change byte ordering, breaking the signature. That's why this handler
reads `await request.body()` and passes those bytes directly to
`stripe.Webhook.construct_event`.
"""

from __future__ import annotations

from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.billing.packs import CreditPack, all_packs, get_pack, get_pack_by_price_id
from app.core.config import settings
from app.core.db import get_session
from app.deps.auth import CurrentUser
from app.models.credit_transaction import CreditTransaction, TransactionType
from app.models.profile import Profile

router = APIRouter()


# ---------------------------------------------------------------------------
# Response / request shapes
# ---------------------------------------------------------------------------


class PackResponse(BaseModel):
    """One credit pack as the frontend sees it.

    Excludes the stripe_price_id because the browser never sends that —
    it sends `pack_id` (our slug) instead. Keeps the Stripe-side
    identifier out of the API contract.
    """

    id: str
    display_name: str
    credits: int
    price_cents: int
    currency: str


class CheckoutRequest(BaseModel):
    """POST /billing/checkout body."""

    pack_id: str


class CheckoutResponse(BaseModel):
    """The URL the browser should navigate to."""

    checkout_url: str


def _pack_to_response(pack: CreditPack) -> PackResponse:
    return PackResponse(
        id=pack.id,
        display_name=pack.display_name,
        credits=pack.credits,
        price_cents=pack.price_cents,
        currency=pack.currency,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/billing/packs", response_model=list[PackResponse], tags=["billing"])
def list_packs() -> list[PackResponse]:
    """Return every configured credit pack, cheapest first.

    Public — no auth required. The catalog is fixed and not user-specific,
    and exposing it lets a future logged-out landing page show pricing.
    """
    return [_pack_to_response(p) for p in all_packs()]


@router.post(
    "/billing/checkout",
    response_model=CheckoutResponse,
    tags=["billing"],
)
def create_checkout_session(
    req: CheckoutRequest,
    user: CurrentUser,
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for the requested pack.

    Returns the hosted Stripe URL. The browser navigates there; Stripe
    handles all card collection, 3DS, etc. On success/cancel, Stripe
    redirects back to `success_url` / `cancel_url` (configured here).

    The webhook (NOT this endpoint) is what actually grants the credits.
    This endpoint just sets up the session.
    """
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured on this server.",
        )

    pack = get_pack(req.pack_id)
    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown credit pack: {req.pack_id!r}",
        )

    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": pack.stripe_price_id, "quantity": 1}],
            success_url=(
                f"{settings.checkout_return_url_base}/?checkout=success"
                "&session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{settings.checkout_return_url_base}/?checkout=cancel",
            # Identify the buyer so the webhook handler knows whose ledger
            # to update. client_reference_id is the standard slot for
            # exactly this — it round-trips through Stripe and shows up on
            # the `session` object in the webhook payload.
            client_reference_id=str(user.id),
            # Snapshot the pack_id too in case we ever need it server-side
            # without reverse-looking-up by price_id (e.g. analytics).
            metadata={"pack_id": pack.id, "credits": str(pack.credits)},
        )
    except stripe.StripeError as exc:
        # Surface Stripe's message — they're usually informative
        # (insufficient funds, card declined, etc.) and the browser can
        # show them in an inline error.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {exc.user_message or str(exc)}",
        ) from exc

    if not session.url:
        # Stripe returned a session without a URL — extremely rare, but
        # surfacing it explicitly beats a None-deref later.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe returned a session without a URL.",
        )
    return CheckoutResponse(checkout_url=session.url)


@router.post("/webhooks/stripe", tags=["billing"], include_in_schema=False)
async def stripe_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    """Receive and process Stripe webhook events.

    Excluded from the OpenAPI schema (`include_in_schema=False`) — this
    endpoint is for Stripe only, not for any client. Listing it in
    `/openapi.json` would risk a frontend codegen treating it as a
    callable shape.

    The verification dance:
      1. Read the RAW request body bytes (not the parsed JSON — see file
         docstring).
      2. Pull the `Stripe-Signature` header.
      3. Call stripe.Webhook.construct_event(body, sig, secret) — it
         verifies the HMAC and returns a parsed Event. Any tampering
         raises SignatureVerificationError; we 400 in that case.
      4. Dispatch on event['type']. We only handle one event today
         (`checkout.session.completed`); everything else returns 200
         "ack" so Stripe stops sending it. Returning a non-2xx for an
         unhandled event would just make Stripe retry forever.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Stripe webhook secret is not configured. Set "
                "STRIPE_WEBHOOK_SECRET (from `stripe listen` or the Stripe "
                "dashboard) and restart."
            ),
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        # stripe's construct_event is untyped in stripe-python 15.x; cast
        # the call so mypy doesn't complain in strict mode.
        event = stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as exc:
        # Malformed payload — Stripe wouldn't send this in practice, but
        # a misconfigured proxy could.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {exc}",
        ) from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature: {exc}",
        ) from exc

    # stripe.Event is a StripeObject, not a plain dict — `event.get(...)`
    # would shadow into its overloaded `__getattr__` and raise. Bracket
    # access is the supported idiom and returns the raw value.
    event_type = event["type"]
    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event, session)

    # Everything else: ack and move on. Stripe sends a lot of events we
    # don't care about (payment_intent.* lifecycle, charge.*, etc.) —
    # returning 200 stops retries.
    return {"received": event_type}


# ---------------------------------------------------------------------------
# Internal handlers
# ---------------------------------------------------------------------------


def _handle_checkout_completed(event: stripe.Event, session: Session) -> None:
    """Grant credits for a completed Checkout Session.

    The session object in the webhook payload has:
      - id                  → unique per Checkout; we use it as the
                              CreditTransaction.reference_id idempotency key
      - client_reference_id → user.id (we set this when creating the session)
      - line_items.data[0].price.id → the Stripe price_id, which we map
                              to our credit pack via packs.py
      - payment_status      → "paid" on success; anything else is suspicious

    Idempotency is enforced at the DB layer by the unique constraint on
    (type, reference_id). Re-delivery from Stripe (retry, replay) hits
    IntegrityError on the second insert; we catch and return cleanly.
    """
    checkout_session = event["data"]["object"]

    if checkout_session["payment_status"] != "paid":
        # Stripe normally only fires this event after payment succeeds,
        # but the documented contract allows mode='payment' sessions to
        # complete without payment in rare edge cases. Don't grant credits
        # in that case — just ack.
        return

    session_id = checkout_session["id"]
    # `client_reference_id` is always present on the session payload — we
    # set it ourselves when creating the Checkout Session — but its value
    # can be None on sessions created outside this codepath. Bracket access
    # returns None in that case, which the `not client_reference_id` guard
    # below catches.
    client_reference_id = checkout_session["client_reference_id"]
    if not client_reference_id:
        # We always set client_reference_id when creating the session;
        # absence here means either a session created outside this app
        # or a configuration drift. Surface it via the logs.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"checkout.session.completed has no client_reference_id (session {session_id})",
        )

    # Pull the price_id from the session's line items. Stripe doesn't
    # expand line_items by default, so we have to fetch them explicitly.
    line_items = stripe.checkout.Session.list_line_items(session_id, limit=1)
    if not line_items.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No line items on completed session {session_id}",
        )
    price_id = line_items.data[0].price.id if line_items.data[0].price else None
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} line item has no price",
        )

    pack = get_pack_by_price_id(price_id)
    if pack is None:
        # Stripe accepted a session for a price we don't have in our
        # catalog — most likely a dashboard-side change without updating
        # the .env. Surface loudly.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No credit pack for price_id {price_id}",
        )

    # Update the ledger + cached profile balance atomically. We don't
    # use SELECT FOR UPDATE here because the unique constraint already
    # serialises concurrent webhook deliveries for the same session_id.
    user_id = client_reference_id
    profile = session.exec(
        select(Profile).where(Profile.user_id == user_id)
    ).first()
    if profile is None:
        # User row should exist (they had to be signed in to start
        # checkout), but a deleted account between checkout and webhook
        # is theoretically possible.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No profile for user {user_id}",
        )

    try:
        session.add(
            CreditTransaction(
                user_id=user_id,
                amount=pack.credits,
                type=TransactionType.PURCHASE,
                reference_id=session_id,
            )
        )
        profile.credit_balance += pack.credits
        session.add(profile)
        session.commit()
    except IntegrityError:
        # Duplicate (PURCHASE, session_id) — already processed. Roll back
        # the failed insert + profile bump and ack the event so Stripe
        # stops retrying.
        session.rollback()
