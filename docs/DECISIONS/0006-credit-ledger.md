# ADR 0006: Credit ledger over mutable balance

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app has a credit system: users buy credits (Stripe), spend credits (generations). Two ways to store this:
- **Mutable balance:** `profiles.credit_balance INTEGER` — incremented on purchase, decremented on spend
- **Ledger:** `credit_transactions` table with one row per credit movement — balance is `SUM(amount)` or a cached denormalization

This decision affects how Stripe webhooks, generation actions, and refunds are implemented.

## Decision

Use a **credit ledger** as the source of truth.

```
credit_transactions
  id            uuid pk
  user_id       uuid fk
  amount        integer        -- positive for credit, negative for debit
  type          enum           -- 'purchase' | 'generation' | 'refund' | 'starter_bonus' | 'admin_grant'
  reference_id  text           -- Stripe session id, generation id, etc. (for idempotency)
  created_at    timestamptz
```

`profiles.credit_balance` exists as a cached denormalization, updated in the same transaction as the ledger insert. Reads use the cached column; writes go through the ledger.

## Consequences

**Positive:**
- Complete audit trail — every credit movement is queryable forever
- Idempotency built in — `reference_id` unique constraint per type prevents double-crediting on Stripe webhook retries
- Refunds are first-class (insert a `refund` row) instead of inverse mutations
- Reconciliation with Stripe is straightforward
- Dev user's "unlimited credits" can be modeled as `Infinity` at the read layer without polluting the ledger

**Negative:**
- One extra insert per credit movement vs a single `UPDATE balance` query — negligible at any reasonable scale
- Slight complexity over a mutable column

## Alternatives considered

- **Mutable balance only:** Rejected because Stripe webhooks can fire multiple times for the same event, and without an idempotency key we'd double-credit. The fix for that is essentially a ledger anyway.
- **Pure ledger (no cached balance):** Rejected because `SELECT SUM(amount) FROM credit_transactions WHERE user_id = ?` becomes slow as a user accumulates thousands of generations. The cached column on `profiles` is updated transactionally with the insert.
