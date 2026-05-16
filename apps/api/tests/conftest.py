"""pytest configuration loaded before any test or app import.

We set a dummy DATABASE_URL so that `app.core.config.settings` can be
constructed without a real .env present. Pydantic only validates the URL
syntax, not reachability. Tests that actually hit the database must use a
real test DB or mock the session dependency.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test_db",
)
os.environ.setdefault(
    "REDIS_URL",
    "redis://localhost:6379/0",
)
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-not-used-for-real-tokens",
)
