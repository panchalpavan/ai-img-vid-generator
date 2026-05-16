"""User table — one row per Google identity that has signed in.

Provisioned just-in-time on the first authenticated request from a new user
(see Sprint 1.3). The `google_sub` column stores Google's `sub` claim — the
stable per-user identifier that does not change if the user changes their
email.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Email is unique but mutable on Google's side (rare but possible).
    # Indexed because it's the natural lookup key from the JWT email claim.
    email: str = Field(unique=True, index=True, max_length=320)
    name: str | None = Field(default=None, max_length=255)
    image_url: str | None = Field(default=None, max_length=2048)
    # Google's stable subject identifier from the JWT `sub` claim.
    # Nullable for now because Sprint 1.3 will start populating it; once
    # populated it never changes for that Google account.
    google_sub: str | None = Field(default=None, unique=True, index=True, max_length=255)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
