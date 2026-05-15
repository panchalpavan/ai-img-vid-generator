# ADR 0003: Supabase free Postgres for development

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app needs a Postgres database during development at zero cost. Options:
- **Supabase free Postgres** — 500MB free, indefinite (with inactivity pause)
- **Neon free tier** — 0.5GB free, autosuspend
- **Cloud SQL** — ~$7/mo minimum, not free
- **Local Postgres via Docker** — free but no remote access

User wants zero dev spend and plans to migrate to Cloud SQL in Sprint 7 when deploying to GCP.

## Decision

Use **Supabase free Postgres** as the development database, accessed via raw `DATABASE_URL` connection string. **Do not use the Supabase JS client or Supabase Auth.**

Drizzle ORM connects directly via the connection string — Supabase is effectively just hosting Postgres.

## Consequences

**Positive:**
- Zero cost during development
- Generous free tier (500MB) — sufficient for thousands of users in dev
- pgvector extension available if Reference Library RAG (D8) is chosen
- Migration to Cloud SQL is a single env-var change (`DATABASE_URL`) plus running migrations — no code changes

**Negative:**
- Free tier pauses after 7 days of inactivity (resumable, brief delay)
- Connection pooling required at scale (Supabase provides Supavisor)
- Not GCP-native — Sprint 7 introduces the migration

## Alternatives considered

- **Neon:** Comparable free tier, branching support is a nice feature. Either would work — Supabase chosen because it includes pgvector by default for the potential RAG path.
- **Cloud SQL from day one:** Rejected — costs money during a long development period before there are real users.
- **Local Docker Postgres:** Rejected — adds setup friction for a solo developer and complicates sharing schema with hosted previews.
