"""GET /me — returns the current user + credit balance.

Provisioning of new users happens transparently inside `get_current_user`
(see app/deps/auth.py). By the time a route handler runs, the User row
always exists.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.deps.auth import CurrentUser
from app.models.profile import Profile

router = APIRouter()


class MeResponse(BaseModel):
    """Shape of GET /me."""

    id: UUID
    email: str
    name: str | None
    image_url: str | None
    balance: int


# A safely large number used to represent "unlimited" credits for the dev
# user. Big enough that no one can blow through it; not so big that an int
# overflow could surprise us downstream.
_DEV_INFINITE_BALANCE = 10**9


@router.get("/me", response_model=MeResponse, tags=["me"])
def me(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> MeResponse:
    """Return the authenticated user's profile + credit balance.

    Dev bypass: if the user's email matches `DEV_EMAIL`, the reported
    balance is effectively infinite. The actual `profiles.credit_balance`
    in the DB is unchanged — this is purely a read-time substitution so
    the dev never has to top up credits while developing.
    """
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    balance = profile.credit_balance if profile is not None else 0

    if settings.dev_email and user.email == settings.dev_email:
        balance = _DEV_INFINITE_BALANCE

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        image_url=user.image_url,
        balance=balance,
    )
