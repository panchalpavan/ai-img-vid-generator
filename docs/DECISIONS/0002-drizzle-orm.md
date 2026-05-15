# ADR 0002: Drizzle ORM over Prisma

**Status:** **SUPERSEDED by ADR-0008** (2026-05-16)
**Original date:** 2026-04-28

## Why superseded

The architecture moved from a Next.js monolith (with Drizzle as the TypeScript ORM) to a two-service topology where a separate FastAPI backend owns the database. With Python owning DB access, a Python-native ORM is required. See ADR-0008 (SQLModel + Alembic).

The reasoning in the original Drizzle ADR — favouring lightweight, no-cold-start-penalty SQL generation — still applies in principle but no longer maps to the chosen stack.

---

## Original content (preserved for history)

The app needs a TypeScript-friendly way to talk to Postgres. Drizzle was chosen over Prisma for:
- No query engine binary — smaller package, no cold-start cost on serverless
- Inspectable generated SQL
- Type safety without a separate `prisma generate` step

This decision held while the entire backend was inside Next.js. When the backend was split out to FastAPI (ADR-0007), Drizzle was dropped in favour of SQLModel.
