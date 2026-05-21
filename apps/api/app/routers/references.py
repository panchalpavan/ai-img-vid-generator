"""References API — user-uploaded image refs (Sprint 4A.3).

Three-step direct-upload flow:

  1. POST /references/presign
       Browser asks for a short-lived signed PUT URL. Backend validates the
       filename / size / content type, mints a reference_id + R2 key, and
       returns the upload URL + the public read URL. No DB row yet.

  2. PUT <upload_url> (browser → R2 directly)
       Backend is not involved. The signed URL is bound to the exact key,
       content-type, and content-length we signed for; R2 rejects anything
       else. CORS on the bucket lets the browser do this cross-origin.

  3. POST /references/{reference_id}/complete
       Browser tells the backend the upload finished. Backend HEADs R2 to
       confirm the object exists with the expected size, then INSERTs the
       Reference row. From here on, the ref is visible in the gallery and
       usable as input to image-to-image generation (Sprint 4A.4).

Two read endpoints round it out:
  - GET /references          → list current user's refs, newest first
  - DELETE /references/{id}  → remove from R2 + DB

What this design deliberately doesn't do:
  - No PENDING row in step 1. If a user abandons the flow we end up with
    an orphaned R2 object but no DB row pointing at it — cleanup is a
    future scheduled task. The trade-off: a tiny bit of garbage in R2
    instead of phantom rows the user sees.
  - No virus / content-policy scan. Out of scope for dev; would slot in
    between step 2 and step 3 if needed.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, desc, select

from app.core.db import get_session
from app.core.storage import (
    delete_object,
    generate_presigned_upload_url,
    head_object,
    public_url_for,
)
from app.deps.auth import CurrentUser
from app.models.reference import Reference

router = APIRouter()

# Validation knobs. Kept module-local for now — we'll graduate them to
# settings if we ever want per-environment overrides.
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB ceiling on a single reference upload
_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
_PRESIGN_TTL_SECONDS = 300  # 5 minutes — long enough for a slow connection
# Extension we use in the R2 key. Derived from the content type, not the
# filename, so a user uploading "cat.JPG" lands at "....jpg" (predictable
# casing) and a user lying about the extension can't fool us.
_CONTENT_TYPE_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class PresignRequest(BaseModel):
    """What the browser sends to /references/presign before uploading."""

    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=1)


class PresignResponse(BaseModel):
    """Everything the browser needs to perform the direct PUT to R2."""

    reference_id: UUID
    upload_url: str
    public_url: str
    key: str
    content_type: str
    size_bytes: int
    expires_in_seconds: int


class CompleteRequest(BaseModel):
    """Sent after the browser finishes the direct PUT."""

    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=1)
    key: str = Field(..., max_length=512)


class ReferenceResponse(BaseModel):
    """Public-facing shape of a Reference row."""

    id: UUID
    public_url: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


def _to_response(row: Reference) -> ReferenceResponse:
    return ReferenceResponse(
        id=row.id,
        public_url=row.public_url,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
    )


def _validate_upload_shape(content_type: str, size_bytes: int) -> None:
    """Shared validation for presign + complete. Raises HTTPException on bad input."""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported content type {content_type!r}. "
                f"Allowed: {sorted(_ALLOWED_CONTENT_TYPES)}."
            ),
        )
    if size_bytes > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_bytes} exceeds limit of {_MAX_BYTES} bytes.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/references/presign",
    response_model=PresignResponse,
    tags=["references"],
)
def presign_reference_upload(
    req: PresignRequest,
    user: CurrentUser,
) -> PresignResponse:
    """Mint a signed PUT URL for the browser to upload directly to R2."""
    _validate_upload_shape(req.content_type, req.size_bytes)

    reference_id = uuid4()
    ext = _CONTENT_TYPE_TO_EXT[req.content_type]
    # User scope baked into the key so a future cleanup job can scope by
    # prefix when listing orphans for a deleted user.
    key = f"references/{user.id}/{reference_id}.{ext}"

    upload_url = generate_presigned_upload_url(
        key=key,
        content_type=req.content_type,
        content_length=req.size_bytes,
        expires_in_seconds=_PRESIGN_TTL_SECONDS,
    )

    return PresignResponse(
        reference_id=reference_id,
        upload_url=upload_url,
        public_url=public_url_for(key),
        key=key,
        content_type=req.content_type,
        size_bytes=req.size_bytes,
        expires_in_seconds=_PRESIGN_TTL_SECONDS,
    )


@router.post(
    "/references/{reference_id}/complete",
    response_model=ReferenceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["references"],
)
def complete_reference_upload(
    reference_id: UUID,
    req: CompleteRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> ReferenceResponse:
    """Verify the R2 upload and create the Reference row.

    HEAD on R2 protects us from the client lying — without it a malicious
    user could call /complete without uploading and end up with a DB row
    pointing at nothing.

    Also checks that the user_id in the R2 key matches the authenticated
    user — defense-in-depth: the key was minted by /presign with this user's
    ID, but if a key from another user's presign somehow leaks we still
    refuse to associate the row with the wrong user.
    """
    _validate_upload_shape(req.content_type, req.size_bytes)

    expected_prefix = f"references/{user.id}/"
    if not req.key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Key does not belong to the authenticated user.",
        )

    meta = head_object(req.key)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No uploaded object found at the given key. "
                "Did the browser PUT complete successfully?"
            ),
        )

    actual_size = int(meta.get("ContentLength", -1))
    if actual_size != req.size_bytes:
        # Size mismatch usually means a truncated upload or a client lying
        # about the file. Either way we don't trust the row.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Uploaded object size {actual_size} does not match the "
                f"declared size {req.size_bytes}."
            ),
        )

    row = Reference(
        id=reference_id,
        user_id=user.id,
        key=req.key,
        public_url=public_url_for(req.key),
        filename=req.filename,
        content_type=req.content_type,
        size_bytes=req.size_bytes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_response(row)


@router.get(
    "/references",
    response_model=list[ReferenceResponse],
    tags=["references"],
)
def list_references(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReferenceResponse]:
    """List the caller's references, newest first."""
    rows = session.exec(
        select(Reference)
        .where(Reference.user_id == user.id)
        .order_by(desc(Reference.created_at))
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_response(row) for row in rows]


@router.delete(
    "/references/{reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["references"],
)
def delete_reference(
    reference_id: UUID,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete the reference's R2 object and DB row.

    Owner-scoped 404 (same pattern as /generations): we don't leak whether
    a foreign reference exists.
    """
    row = session.get(Reference, reference_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference not found.",
        )
    # Delete R2 first — if it fails we surface that and don't orphan a row
    # pointing at a still-existing object. If the DB delete fails after the
    # R2 delete succeeds we end up with an orphaned row (less harmful;
    # next list call will 404 on render).
    delete_object(row.key)
    session.delete(row)
    session.commit()
