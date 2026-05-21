"""Reference table — user-uploaded image refs for multimodal generation.

A row exists only after we've verified the bytes landed in R2 (via the
`POST /references/{id}/complete` HEAD check). There's no PENDING state:
if an upload never completes, R2 may hold an orphaned object, but no DB
row points at it — so the user never sees a ref that doesn't work.

Cleanup of orphaned R2 objects is deferred to a future scheduled task.
Object keys include the user_id so the cleanup job can scope by prefix
when we add it.

Note: `references` is a reserved word in SQL (used in foreign-key
constraints). Postgres allows it as a table name unquoted in DDL; SQLAlchemy
auto-quotes when it emits ORM SQL. Raw SQL (like a hand-written op.execute
in a migration) must quote it as "references". Logged in docs/GOTCHAS.md.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Reference(SQLModel, table=True):
    __tablename__ = "references"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # R2 object key. Format: `references/<user_id>/<reference_id>.<ext>`.
    # Stored separately from public_url so we can call delete_object(key)
    # without re-parsing the URL, and so a future move to signed reads
    # (where public_url becomes ephemeral) doesn't break deletion.
    key: str = Field(max_length=512)

    # Public r2.dev URL — what the browser uses to render thumbnails AND
    # what we hand to provider adapters as `image_urls` for image-to-image
    # generation. As of writing the bucket is public-read, so this is a
    # stable URL; if we move to signed reads, this column becomes a
    # render-time-resolved value instead.
    public_url: str = Field(max_length=1024)

    # Original filename the user uploaded — purely UI ("Untitled.png" vs
    # "my-brand-logo.png" matters for them, not for us). Capped at 255 to
    # match common filesystem limits.
    filename: str = Field(max_length=255)

    # MIME type and size, captured at upload time. Used by the gallery UI
    # for display ("PNG · 240 KB") and by validation if we re-process the
    # reference later.
    content_type: str = Field(max_length=128)
    size_bytes: int

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), index=True
    )
