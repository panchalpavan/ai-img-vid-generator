"""Database engine and session management.

There is exactly one Engine per process. Engines own a connection pool.
There is one Session per request (created and disposed by `get_session`).
Sessions represent a transactional unit of work.
"""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

# pool_pre_ping=True: SQLAlchemy issues a cheap ping before every checkout.
# This prevents "stale connection" errors when Supabase auto-pauses idle DBs
# or when network blips drop pooled connections.
engine = create_engine(
    str(settings.database_url),
    echo=False,  # set True locally to log every SQL statement
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional session.

    Usage in a route:
        @app.get("/items")
        def list_items(session: Session = Depends(get_session)) -> ...:
            ...

    The `with` block ensures the session is closed (and any open transaction
    rolled back) when the request finishes — even if an exception is raised.
    """
    with Session(engine) as session:
        yield session
