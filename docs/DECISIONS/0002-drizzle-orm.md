# ADR 0002: Drizzle ORM over Prisma

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app needs a TypeScript-friendly way to talk to Postgres. Two mainstream options:
- **Prisma** — most popular, schema-first, generated client with a query engine binary
- **Drizzle ORM** — newer, code-first, generates raw SQL at compile time, no runtime engine

The app uses serverless deployment (Vercel now, Cloud Run later). Cold starts matter.

## Decision

Use **Drizzle ORM**.

Schema lives in `lib/db/schema.ts`. Migrations generated via `drizzle-kit`. Client initialized once per server runtime.

## Consequences

**Positive:**
- No query engine binary — package size stays small
- No cold-start penalty on serverless (Prisma's historical pain point)
- Generated SQL is inspectable and tuneable
- Type safety without leaving the codebase (no `prisma generate` step required at runtime)
- Migrates cleanly between any Postgres provider (Supabase → Cloud SQL → self-hosted)

**Negative:**
- Smaller community than Prisma — fewer Stack Overflow answers
- Schema-as-code requires understanding of SQL types (Prisma abstracts these)

## Alternatives considered

- **Prisma:** Rejected primarily for serverless cold-start cost and the bundled engine binary.
- **Raw SQL with `postgres` driver:** Considered but loses type-safety on results without manual typing.
- **Kysely:** Strong type-safe query builder, but Drizzle has better schema migration tooling.
