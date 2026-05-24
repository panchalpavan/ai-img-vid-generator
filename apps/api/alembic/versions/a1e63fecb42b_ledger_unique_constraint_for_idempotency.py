"""ledger_unique_constraint_for_idempotency

Revision ID: a1e63fecb42b
Revises: 352086a915a3
Create Date: 2026-05-24 15:57:06.458007

Add a UNIQUE constraint on (type, reference_id) to credit_transactions.
This is the foreshadowed-in-the-docstring constraint that turns the
ledger into a true idempotency primitive — required for Sprint 5's
Stripe webhook handling.

Why this matters: Stripe retries webhooks aggressively (up to 3 days with
backoff) on any non-2xx response. Without DB-level uniqueness, a slow
response that Stripe retries while the first call is still processing
would double-grant credits. The unique constraint makes the second
INSERT fail with an IntegrityError, which the webhook handler converts
into a 200 "already processed, no-op" response.

Postgres treats NULL as distinct in unique constraints by default — so
the existing rows with reference_id IS NULL (STARTER_BONUS today, future
ADMIN_GRANT) can coexist freely. The constraint only enforces uniqueness
when a reference_id is actually set, which is exactly when we need it:

  - GENERATION + generation_id (the SELECT FOR UPDATE already prevents
    double-debit, but the constraint is a belt-and-braces backstop)
  - REFUND + generation_id (one refund per failed generation)
  - PURCHASE + stripe_session_id (new in Sprint 5 — idempotent webhook)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1e63fecb42b"
down_revision: Union[str, Sequence[str], None] = "352086a915a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_credit_transactions_type_reference_id",
        "credit_transactions",
        ["type", "reference_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_credit_transactions_type_reference_id",
        "credit_transactions",
        type_="unique",
    )
