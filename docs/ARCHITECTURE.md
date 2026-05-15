# Architecture

## Topology (locked 2026-05-16)

Two services in a monorepo. Next.js is the frontend + auth shell. FastAPI owns business logic, the database, and all AI orchestration.

```
Browser
  │
  ▼
Next.js (apps/web)                 ← Auth.js issues JWT
  │  Authorization: Bearer <jwt>
  ▼
FastAPI (apps/api)                 ← verifies JWT with shared secret
  │
  ├──► Postgres (Supabase free → Cloud SQL later)
  ├──► R2 (Cloudflare → GCS later)
  ├──► Redis (Celery broker + cache)
  └──► Celery worker (apps/api, separate process)
           │
           ├──► Gemini (Google AI Studio → Vertex AI later)
           └──► Sjinn (Sprint 6)
```

## Stack (locked 2026-05-16)

### Frontend — `apps/web`

| Layer | Technology | Notes |
|-------|------------|-------|
| Framework | Next.js (App Router) | 16.2.4 — see `node_modules/next/dist/docs/` before writing code |
| UI | React 19, Shadcn/UI, Tailwind CSS 4 | Tailwind config is CSS-native (no `tailwind.config.js`) |
| Language | TypeScript (strict) | ^5 |
| Auth | Auth.js (next-auth v5) | Google OAuth, **JWT session strategy** (ADR-0009) |
| Data fetching | TanStack Query | Polls FastAPI, manages cache |
| Generated types | `packages/shared-types` | TS types generated from FastAPI's OpenAPI |
| Package manager | npm | (workspace member) |

### Backend — `apps/api`

| Layer | Technology | Notes |
|-------|------------|-------|
| Framework | FastAPI | OpenAPI auto-generation, async-native |
| Language | Python 3.12 | uv-managed, Ruff for lint/format, mypy for types |
| ORM | SQLModel + Alembic | ADR-0008 — by FastAPI's author, Pydantic-native |
| Validation | Pydantic v2 | Built into FastAPI |
| Job queue | Celery 5 + Redis | ADR-0010 |
| Storage SDK | boto3 (R2 / S3 API) | |
| AI SDK | google-generativeai (Python) | Official Gemini SDK |
| Stripe SDK | stripe (Python) | |
| Auth | PyJWT | Verifies tokens minted by Auth.js |
| Testing | pytest + httpx | |

### Infrastructure (dev — zero cost)

| Service | Provider | Notes |
|---------|----------|-------|
| Database | Supabase free Postgres | Connection string only; NOT the Supabase client (ADR-0003) |
| Storage | Cloudflare R2 | 10GB free, no egress (ADR-0004) |
| AI | Google AI Studio | Free Gemini tier (ADR-0004) |
| Redis | Local Docker | `docker-compose.yml` at repo root |
| Auth | Google OAuth | Free |

### Infrastructure (Sprint 7 production — TBD per D18)

Candidates: Vercel + Cloud Run, full GCP, or Fly.io. Migration is configuration-level if abstractions hold.

## Repo layout

```
img-vid-generation/
├── apps/
│   ├── web/                    # Next.js
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   │   ├── auth/           # Auth.js config
│   │   │   ├── api/            # Thin client wrapping shared-types
│   │   │   └── query/          # TanStack Query setup
│   │   └── package.json
│   └── api/                    # FastAPI
│       ├── app/
│       │   ├── main.py         # FastAPI app
│       │   ├── deps/           # Dependencies (auth, db)
│       │   ├── routers/        # HTTP routes
│       │   ├── models/         # SQLModel tables
│       │   ├── schemas/        # Pydantic request/response
│       │   ├── providers/      # AI provider adapters (ADR-0005)
│       │   ├── storage/        # R2/S3 abstraction
│       │   ├── tasks/          # Celery tasks
│       │   └── core/           # Config, settings, security
│       ├── alembic/            # Migrations
│       ├── tests/
│       ├── pyproject.toml
│       └── uv.lock
├── packages/
│   └── shared-types/           # Generated TS types from OpenAPI
│       └── api.d.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CONVENTIONS.md
│   ├── GOTCHAS.md
│   ├── SPRINTS.md
│   └── DECISIONS/
├── docker-compose.yml          # Redis (and future local services)
├── package.json                # npm workspaces root
└── .claude/
```

## Key architectural principles

1. **Two services, one repo.** Next.js never talks to the database directly. Every read/write goes through FastAPI.
2. **Auth is JWT-based.** Auth.js issues, FastAPI verifies. No shared session table, no database coupling between services. (ADR-0009)
3. **Async by default.** Generations are Celery tasks. Even fast Gemini calls go through the queue so the codepath is identical to Sjinn's slow path. (ADR-0010)
4. **OpenAPI is the contract.** FastAPI generates it for free. TypeScript types are derived, not hand-written. No drift between frontend and backend.
5. **Adapter pattern for providers.** AI, storage, DB all sit behind thin interfaces. Provider swaps are config changes. (ADR-0005)
6. **Credit ledger, not mutable balance.** Every credit movement is an audit row; balance is a cached denormalization. (ADR-0006)
7. **No proprietary clients.** No Supabase JS client, no Firebase SDK. Connection strings + open-source libs only. (ADR-0001, ADR-0003)
8. **Server Components by default** (in `apps/web`). `"use client"` at the lowest possible boundary.

## Request flow examples

### Login (first time)

1. User clicks "Sign in with Google" → Auth.js redirects to Google OAuth.
2. Google redirects back → Auth.js verifies, mints a JWT containing `{email, name, sub}`, sets it as an HttpOnly cookie.
3. User loads protected page → Auth.js validates the JWT, attaches it to outgoing fetches.
4. Frontend calls `GET /me` on FastAPI with `Authorization: Bearer <jwt>`.
5. FastAPI verifies JWT signature using `JWT_SECRET`, decodes email.
6. If no `User` row for that email → create one, create `Profile` with 0 credits.
7. Return `{user, profile, balance}` → frontend renders navbar with credit badge.

### Generation submit (Gemini, async)

1. User submits form in Next.js. Frontend posts to FastAPI `POST /generations` with JWT.
2. FastAPI validates input, creates `generations` row (status=`pending`), enqueues Celery task, returns `{id, status: "pending"}`.
3. Frontend (TanStack Query) starts polling `GET /generations/{id}`.
4. Celery worker picks up task: loads row → calls Gemini → uploads result to R2 → updates row to `done` with `result_url`.
5. Frontend's next poll returns `status: "done"` with `result_url` → renders image.
6. In the same DB transaction as `done`: insert a `credit_transactions` debit row and update `profile.credit_balance`.

### Stripe webhook (Sprint 5)

1. User completes Stripe Checkout (initiated via FastAPI session creation endpoint).
2. Stripe POSTs to FastAPI `/webhooks/stripe` with signature header.
3. FastAPI verifies signature using `STRIPE_WEBHOOK_SECRET`.
4. If `checkout.session.completed` and `reference_id` not yet in `credit_transactions`: insert credit row, update profile balance. Idempotent.

## Scaling path (designed for, not built yet)

- **Connection pooler** in front of Postgres (PgBouncer / Supavisor / pgbouncer in Cloud SQL)
- **Celery workers scale horizontally** — add more workers, no app changes
- **Redis Sentinel or managed Redis** (Upstash, Memorystore) once dev → prod
- **CDN in front of R2/GCS** for public result URLs
- **Read replicas on Postgres** once write load justifies it

## Adding new functionality

- **New API endpoint:** add a route to `apps/api/app/routers/`, define request/response Pydantic schemas, write the handler, regenerate TS types in `apps/web`, consume.
- **New AI provider:** add a module to `apps/api/app/providers/` implementing the adapter interface; register in `__init__.py`; no other code touches.
- **New page in Next.js:** create a folder under `apps/web/app/` with `page.tsx`. Layouts cascade.
