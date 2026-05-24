"""Stripe billing — credit pack purchases.

Two source-of-truth layers:

  - Stripe owns the **money side**: Products + Prices + Checkout Sessions live
    in Stripe and are referenced by price_id (a stable string like
    `price_1TaZ7k...`). All currency/amount/tax logic happens there.

  - We own the **credits side**: how many app credits each price_id grants.
    Stripe doesn't know "this $5 buys 100 credits" — that mapping lives in
    `packs.py` here, keyed by price_id.

The webhook flow ties them together: on `checkout.session.completed`, we look
up the line item's price_id in our catalog, grant that many credits, and
insert a CreditTransaction(type=PURCHASE) keyed on the Stripe session id for
idempotency.
"""
