# ADR 0001: Auth.js over Supabase Auth and Firebase Auth

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app needs Google OAuth login. Three viable options exist:
- **Supabase Auth** — bundled with Supabase, fastest DX, ties auth to Supabase infra
- **Firebase Auth** — Google's auth service, ties auth to Firebase
- **Auth.js (next-auth v5)** — open-source, runs on any DB, 50+ providers

The user has explicitly stated they want to avoid vendor lock-in. The project's stated goal is also learning every layer.

## Decision

Use **Auth.js (next-auth v5)** with the Google OAuth provider. Session storage uses Drizzle adapter pointed at the Postgres database (whichever Postgres is configured via `DATABASE_URL`).

## Consequences

**Positive:**
- Zero auth vendor lock-in — Auth.js is open source, Apache 2.0 licensed
- Moving from Supabase Postgres → Cloud SQL → self-hosted Postgres in the future does not require an auth migration
- Learning auth at a lower level than a turnkey service

**Negative:**
- ~30 minutes more setup vs Supabase Auth (configuring providers, session strategy, adapter)
- No built-in auth UI (Shadcn covers this)

## Alternatives considered

- **Supabase Auth:** Rejected because it ties auth to Supabase. Migrating off Supabase later means migrating user sessions and re-authenticating users.
- **Firebase Auth:** Rejected for the same lock-in reason. Also, Firebase Auth + non-Firebase backend is awkward (token verification on every request).
- **Clerk:** Excellent DX but paid past a small free tier; user wants zero spend during development.
