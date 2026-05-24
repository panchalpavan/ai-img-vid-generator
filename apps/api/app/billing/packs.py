"""Credit pack catalog — single source of truth for "what each price grants."

Stripe stores Products and Prices, but it has no idea that buying our $5
pack should grant 100 in-app credits — that's a domain decision, not a
billing one. This module is that mapping.

The catalog is keyed by **pack_id** (our internal string slug) rather than
by Stripe price_id, for two reasons:

  1. The browser sends `pack_id` (a stable, human-meaningful identifier
     like "starter") to `POST /billing/checkout`. We don't want the price_id
     to leak into the API contract because price_ids change if we ever
     archive a price and create a new one with different terms.

  2. We need a reverse lookup too — on webhook receipt, Stripe gives us
     the price_id (from the session's line items). `_BY_PRICE_ID` does
     that lookup in O(1).

If the Stripe env vars aren't set (dev without Stripe configured), the
catalog is empty rather than raising — keeps the rest of the app bootable
without a Stripe key.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class CreditPack:
    """One purchasable bundle of credits."""

    id: str  # internal slug — e.g. "starter"
    display_name: str  # what the UI shows — e.g. "Starter Pack"
    credits: int  # how many credits the buyer receives
    price_cents: int  # display-only mirror of Stripe's amount
    currency: str  # ISO 4217 lowercase, mirrors Stripe
    stripe_price_id: str  # the Stripe Price the Checkout Session will reference


# The catalog. Edit here when you change prices in the Stripe dashboard —
# the price IDs must match what's in the Stripe dashboard exactly, or the
# Checkout Session creation will error out.
#
# `price_cents` and `currency` are display-only mirrors so the frontend can
# render "100 credits / $5" without a Stripe API roundtrip on every page
# load. The authoritative number is whatever Stripe charges; if these drift
# from Stripe the user briefly sees a stale price, but the actual charge is
# always correct.
def _build_catalog() -> dict[str, CreditPack]:
    catalog: dict[str, CreditPack] = {}
    if settings.stripe_price_id_starter:
        catalog["starter"] = CreditPack(
            id="starter",
            display_name="Starter Pack",
            credits=100,
            price_cents=500,
            currency="usd",
            stripe_price_id=settings.stripe_price_id_starter,
        )
    if settings.stripe_price_id_pro:
        catalog["pro"] = CreditPack(
            id="pro",
            display_name="Pro Pack",
            credits=500,
            price_cents=2000,
            currency="usd",
            stripe_price_id=settings.stripe_price_id_pro,
        )
    if settings.stripe_price_id_studio:
        catalog["studio"] = CreditPack(
            id="studio",
            display_name="Studio Pack",
            credits=2000,
            price_cents=6000,
            currency="usd",
            stripe_price_id=settings.stripe_price_id_studio,
        )
    return catalog


PACKS: dict[str, CreditPack] = _build_catalog()
_BY_PRICE_ID: dict[str, CreditPack] = {p.stripe_price_id: p for p in PACKS.values()}


def get_pack(pack_id: str) -> CreditPack | None:
    """Look up a pack by our internal slug. Returns None if unknown."""
    return PACKS.get(pack_id)


def get_pack_by_price_id(price_id: str) -> CreditPack | None:
    """Reverse lookup — what pack does this Stripe price_id correspond to?

    Used inside the webhook handler. Stripe gives us the price_id from the
    session's line items; we need to know how many credits to grant.
    Returns None if the price_id isn't one of ours (which would mean
    someone created a Checkout Session against a price we don't recognise,
    most likely a misconfiguration; the webhook handler should error out
    visibly in that case rather than silently grant zero credits).
    """
    return _BY_PRICE_ID.get(price_id)


def all_packs() -> list[CreditPack]:
    """Every configured pack, in display order (cheapest → most expensive)."""
    return sorted(PACKS.values(), key=lambda p: p.price_cents)
