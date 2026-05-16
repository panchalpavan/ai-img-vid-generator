"""CreditTransaction table — the credit ledger (ADR-0006).

Every credit movement in the system creates a row here. Balance is derived
as `SUM(amount) WHERE user_id = ?`, with `profiles.credit_balance` acting
as a cached denormalization for fast reads.

`amount` is signed:
  - positive  → credit (purchase, starter bonus, admin grant, refund-in)
  - negative  → debit  (generation cost, refund-out)

`reference_id` is the idempotency key for the transaction's source event.
For purchases it stores the Stripe checkout session ID; for generation
debits it stores the generation ID. A future Sprint will add a unique
constraint on `(type, reference_id)` once the actual reference shapes are
known — that's what prevents Stripe's webhook retries from double-crediting.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class TransactionType(StrEnum):
    """Why a credit movement happened.

    The Python Enum gives us type safety at the application layer; the DB
    column is plain VARCHAR (forced via `sa_column=Column(String(...))` on
    the `type` field below). Using VARCHAR sidesteps the well-known pain of
    altering Postgres ENUM types via Alembic: adding a new transaction type
    later requires only a Python change, no schema migration.
    """

    PURCHASE = "purchase"
    GENERATION = "generation"
    REFUND = "refund"
    STARTER_BONUS = "starter_bonus"
    ADMIN_GRANT = "admin_grant"


class CreditTransaction(SQLModel, table=True):
    __tablename__ = "credit_transactions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    amount: int  # signed: positive = credit, negative = debit
    # sa_column forces VARCHAR(32) instead of a Postgres ENUM type, even
    # though TransactionType is a Python Enum (see class docstring).
    type: TransactionType = Field(
        sa_column=Column(String(32), nullable=False, index=True)
    )
    reference_id: str | None = Field(default=None, index=True, max_length=255)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
