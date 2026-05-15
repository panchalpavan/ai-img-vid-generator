# ADR 0009: JWT-based auth between Next.js and FastAPI

**Status:** Accepted
**Date:** 2026-05-16

## Context

Two services need to agree on user identity. Options:

- **Shared JWT.** Auth.js mints a JWT after Google OAuth completes. Frontend sends it as `Authorization: Bearer ...`. FastAPI verifies using a shared secret.
- **Shared database session table.** Both services read session rows from Postgres. Auth.js writes them; FastAPI looks them up.
- **Dedicated auth provider.** Clerk or Auth0 mints tokens; both services verify against the provider's public key.
- **FastAPI-only auth.** Next.js becomes a dumb proxy. Rejected immediately because Auth.js's frontend integration is the whole point of using it.

## Decision

Use **shared JWT** (Option A).

- Auth.js v5 is configured with `session: { strategy: "jwt" }`
- Auth.js JWT signing secret is `JWT_SECRET` — same env var is loaded by FastAPI
- Algorithm: HS256 (HMAC, symmetric — both services have the secret)
- Token claims include: `sub` (provider ID), `email`, `name`, `exp` (expiration)
- Token lifetime: 30 days (Auth.js default), refreshed on activity
- FastAPI dependency `get_current_user` extracts and verifies the bearer token on protected routes
- On first verified request from a new user, FastAPI provisions a `User` row keyed by email

## Consequences

**Positive:**
- Clean service boundary — FastAPI never queries an Auth.js session table
- Stateless verification — FastAPI scales horizontally without shared session state
- Industry-standard pattern that transfers to any future job or service
- Redis (already in the stack for Celery, ADR-0010) provides an obvious place for a future token blacklist if revocation becomes needed

**Negative:**
- **Revocation is not instant.** A compromised token is valid until expiry unless we add a blacklist.
- Long expiry means longer exposure on token leak. Mitigation: short access tokens + refresh tokens — added if/when needed.
- Shared secret must be rotated in both services together.

## Alternatives considered

- **DB session table.** Rejected because it couples FastAPI to Auth.js's session schema. If Auth.js changes its schema (which has happened across major versions), FastAPI breaks.
- **Asymmetric JWT (RS256).** Considered. Cleaner separation (Auth.js holds private key, FastAPI holds public key) but adds key management overhead with no real benefit for a single-tenant app. Revisit if multiple services need to verify.
- **Clerk / Auth0.** Rejected. Adds a paid vendor and reduces the auth-related learning. Conflicts with the explicit no-spend dev stance.

## Implementation notes

- `JWT_SECRET` lives in the root `.env.example` and is consumed by both apps
- FastAPI uses `PyJWT` (not `python-jose`) — actively maintained and the canonical choice in 2026
- Test path: a `/api/dev/token` endpoint in Auth.js (dev mode only) prints the current JWT for use with curl/Postman against FastAPI
