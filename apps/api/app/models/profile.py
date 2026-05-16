"""Profile table — one row per User, holds the cached credit balance.

ADR-0006 establishes that credit movements live in `credit_transactions`
(the ledger); `profiles.credit_balance` is a denormalization updated in the
same transaction as the ledger insert. Reads use this column; writes go
through the ledger and update this column atomically.

`user_id` is both the primary key and the foreign key to `users.id` — this
enforces the 1:1 relationship at the schema level (a user cannot have two
profiles).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    credit_balance: int = Field(default=0)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
