"""Generation table — one row per submitted generation request.

A row is created in `pending` state by `POST /generations`. The Celery
task `run_generation` (apps/api/app/tasks/generation.py) picks it up,
flips it to `processing`, calls the provider, and lands it at `done` or
`failed`. Frontend polls `GET /generations/{id}` until status is terminal.

The ledger entry for charging the user (CreditTransaction) uses this
row's `id` as its `reference_id` — that's the idempotency key for ADR-0006.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class GenerationStatus(StrEnum):
    """Lifecycle of a generation row.

    Stored as VARCHAR for the same reason TransactionType is — Alembic
    migrations of Postgres ENUMs are notoriously painful.
    """

    PENDING = "pending"      # row created, task not yet picked up
    PROCESSING = "processing"  # worker has picked it up, provider call in flight
    DONE = "done"            # provider returned a result
    FAILED = "failed"        # provider errored or insufficient credits


class Generation(SQLModel, table=True):
    __tablename__ = "generations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # Snapshot of the model that was selected. Not a FK to a models table
    # because models live in the in-memory registry, not the DB.
    model_id: str = Field(max_length=255, index=True)

    # User input. Sprint 4 will add `image_urls jsonb` for multimodal inputs.
    prompt: str

    # Lifecycle. Forced VARCHAR via sa_column (same trick as TransactionType).
    status: GenerationStatus = Field(
        sa_column=Column(String(32), nullable=False, index=True)
    )

    # Result fields — exactly one of these is set on success, depending on
    # the model's output_type. result_url stores either an R2 URL (when
    # binary uploads land in a later sprint) or a data URI as a stopgap.
    result_text: str | None = None
    result_url: str | None = Field(default=None, max_length=4096)

    # Human-readable error captured when status == FAILED.
    error: str | None = Field(default=None, max_length=2048)

    # Snapshot of the model's cost at submission time. If we change a
    # model's cost in the registry later, historical generations still
    # show what they were charged.
    cost_in_credits: int

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), index=True
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
