"""FastAPI dependencies for authentication.

Provides `get_current_user` — a Depends-able callable that:
1. Extracts the `Authorization: Bearer <jwt>` header from the request.
2. Verifies the JWT signature using JWT_SECRET (same key Auth.js signs with — ADR-0009).
3. Reads `email`, `name`, `picture`, `sub` claims from the payload.
4. Just-In-Time provisions a `User` + `Profile` row on the first sign-in for a
   given email. If FREE_STARTER_CREDITS is configured, also inserts a
   STARTER_BONUS row in the credit ledger (ADR-0006).
5. Returns the `User` SQLModel instance.

Routes that need authentication add this as a dependency:

    @router.get("/something")
    def something(user: User = Depends(get_current_user)) -> ...:
        ...
"""

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.models.credit_transaction import CreditTransaction, TransactionType
from app.models.profile import Profile
from app.models.user import User

# HTTPBearer auto-extracts the "Authorization: Bearer <token>" header.
# auto_error=False means we raise our own 401 with a useful message instead
# of the default empty 403.
_bearer_scheme = HTTPBearer(auto_error=False)


def _provision_new_user(
    session: Session,
    *,
    email: str,
    name: str | None,
    image_url: str | None,
    google_sub: str | None,
) -> User:
    """Insert User + Profile (+ optional STARTER_BONUS) in one transaction.

    Called only on the first authenticated request for a given email. The
    transaction is committed by the caller after a successful insert.
    """
    user = User(email=email, name=name, image_url=image_url, google_sub=google_sub)
    session.add(user)
    # flush() assigns user.id without committing, so we can FK to it below
    # in the same transaction.
    session.flush()

    profile = Profile(user_id=user.id, credit_balance=settings.free_starter_credits)
    session.add(profile)

    if settings.free_starter_credits > 0:
        session.add(
            CreditTransaction(
                user_id=user.id,
                amount=settings.free_starter_credits,
                type=TransactionType.STARTER_BONUS,
            )
        )

    session.commit()
    session.refresh(user)
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Resolve the current user from the bearer JWT, provisioning if new.

    Raises 401 if:
      - the header is missing or malformed,
      - the JWT signature/expiration verification fails,
      - the token has no `email` claim (we key users by email).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            # Auth.js doesn't set aud/iss claims by default; skip those checks.
            options={"verify_aud": False, "verify_iss": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None

    email = payload.get("email")
    if not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing or malformed email claim",
        )

    name = payload.get("name") if isinstance(payload.get("name"), str) else None
    image_url = payload.get("picture") if isinstance(payload.get("picture"), str) else None
    google_sub = payload.get("sub") if isinstance(payload.get("sub"), str) else None

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        # First sign-in for this email — provision in one transaction.
        return _provision_new_user(
            session,
            email=email,
            name=name,
            image_url=image_url,
            google_sub=google_sub,
        )

    # Existing user — refresh mutable claims if Google sent different values.
    # Keeps name/avatar in sync if the user updates them on Google's side.
    changed = False
    if name is not None and user.name != name:
        user.name = name
        changed = True
    if image_url is not None and user.image_url != image_url:
        user.image_url = image_url
        changed = True
    if google_sub is not None and user.google_sub != google_sub:
        user.google_sub = google_sub
        changed = True
    if changed:
        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


# Convenience type alias for route signatures.
CurrentUser = Annotated[User, Depends(get_current_user)]
