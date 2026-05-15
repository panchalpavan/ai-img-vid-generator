# ADR 0008: SQLModel + Alembic over Drizzle

**Status:** Accepted (supersedes ADR-0002)
**Date:** 2026-05-16

## Context

With the backend split into a separate FastAPI service (ADR-0007), Python owns database access. A Python-native ORM is required. The candidates in 2026 are:

- **SQLAlchemy 2.0** — the canonical Python ORM, mature, verbose, full SQL control
- **SQLModel** — by FastAPI's author Sebastián Ramírez; combines Pydantic + SQLAlchemy so model classes are simultaneously DB tables and request/response schemas
- **Tortoise ORM** — async-native, simpler than SQLAlchemy, smaller ecosystem
- **Piccolo** — async, smaller still
- **Raw SQL with asyncpg** — full control, zero ORM overhead, but no type safety on results

## Decision

Use **SQLModel** for models and queries, **Alembic** for migrations.

SQLModel sits on top of SQLAlchemy 2.0 and Pydantic v2. Models are defined once and serve as both database tables and Pydantic schemas (with `table=True` toggling the SQL aspect). Alembic generates and applies migrations against any Postgres connection.

## Consequences

**Positive:**
- Single source of truth: one class is both table definition and serialization schema
- Type safety end-to-end: queries return typed model instances; FastAPI responses validate against them
- Author of FastAPI built this specifically to solve the FastAPI ↔ ORM friction
- Alembic is the mature, battle-tested migration tool in Python — every Python backend job uses it
- Migrating between Postgres providers (Supabase → Cloud SQL → self-hosted) is a connection string change

**Negative:**
- SQLModel is younger than SQLAlchemy proper — smaller community, some edge cases require dropping to SQLAlchemy under the hood
- Some advanced relationships are awkward (improving steadily, but worth knowing)
- Couples Pydantic and SQLAlchemy versions tightly — major upgrades need coordination

## Alternatives considered

- **SQLAlchemy 2.0 directly.** Considered. Rejected because the duplication between SQLAlchemy models and Pydantic schemas is exactly what SQLModel solves. SQLAlchemy is the right pick for advanced use cases or teams that already know it deeply; for greenfield + learning, SQLModel wins.
- **Tortoise ORM.** Async-first which is appealing, but smaller ecosystem and less migration tooling maturity than Alembic.
- **Raw asyncpg.** Considered for the no-magic learning value. Rejected because the boilerplate cost slows the learning of every other concept.
