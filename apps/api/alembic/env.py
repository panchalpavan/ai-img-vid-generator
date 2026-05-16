"""Alembic migration environment.

Customized from the default scaffold to:
1. Read DATABASE_URL from our Pydantic Settings (which reads .env), so
   migrations and the running app always agree on the target database.
2. Use SQLModel's metadata as the autogenerate target, so `alembic revision
   --autogenerate` can detect schema changes from SQLModel classes.
"""

from logging.config import fileConfig

from alembic import context
from app.core.config import settings
from app.models import credit_transaction, profile, user  # noqa: F401
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# The `from app.models import ...` line above is a side-effect import: every
# module that defines a SQLModel table must be imported so the tables get
# registered on SQLModel.metadata before autogenerate introspects it.
# Add a new entry every time a new model file is created.

# Alembic Config object — wraps alembic.ini.
config = context.config

# Inject the URL from our settings so we don't duplicate the connection
# string in alembic.ini.
config.set_main_option("sqlalchemy.url", str(settings.database_url))

# Configure Python logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for `alembic revision --autogenerate`.
# Empty until Sprint 1.2 adds the first model — autogenerate will produce
# no-op migrations until then, which is fine.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection.

    Used to generate raw SQL scripts (e.g. for review). Not how we run in
    development — that's online mode.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
