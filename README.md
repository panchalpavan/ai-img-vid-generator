# img-vid-generation

AI image and video generation app. Users describe what they want, the app generates it via Gemini (now) or Sjinn (later), users pay with credits.

This is a **monorepo** containing two services and one shared package.

## Structure

```
img-vid-generation/
├── apps/
│   ├── web/                 # Next.js 16 frontend (Auth.js, Shadcn/UI, TanStack Query)
│   └── api/                 # FastAPI backend (SQLModel, Celery + Redis) — Sprint 0.5.2
├── packages/
│   └── shared-types/        # TS types auto-generated from FastAPI's OpenAPI — Sprint 0.5.4
├── docs/                    # Architecture, ADRs, sprint plan — read this first
└── docker-compose.yml       # Local infra (Redis, etc.) — Sprint 0.5.5
```

## Quick start

```bash
# Install JS dependencies (apps/web and packages/*)
npm install

# Run the frontend (Next.js on http://localhost:3000)
npm run dev:web

# Later, once apps/api exists:
# npm run dev:api      # FastAPI on http://localhost:8000
# npm run dev:worker   # Celery worker
# npm run dev          # All three at once
```

## Tech stack

**Frontend** ([apps/web](apps/web/)): Next.js 16, React 19, TypeScript, Tailwind CSS 4, Auth.js v5, TanStack Query, Shadcn/UI

**Backend** ([apps/api](apps/api/)): Python 3.12, FastAPI, SQLModel, Alembic, Celery, Pydantic v2, PyJWT

**Infrastructure (dev)**: Supabase Postgres (free tier), Cloudflare R2, Redis (Docker), Google AI Studio (Gemini free tier)

## Documentation

| Doc | When to read it |
|-----|-----------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | First — understand the system topology |
| [docs/SPRINTS.md](docs/SPRINTS.md) | Current sprint and what's next |
| [docs/DECISIONS/](docs/DECISIONS/) | Why we chose each piece of the stack (11 ADRs) |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | Code style and naming |
| [docs/GOTCHAS.md](docs/GOTCHAS.md) | Sharp edges in Next.js 16, Tailwind 4, React 19 |
| [apps/web/README.md](apps/web/README.md) | Frontend-specific commands |
| [apps/api/README.md](apps/api/README.md) | Backend-specific commands |

## Project philosophy

- **Learning-driven** — every decision is documented as an ADR with the reasoning, not just the choice
- **Zero-cost development** — free tiers across all services; production migration designed but deferred
- **Adapter pattern everywhere** — AI providers, storage, DB all sit behind thin abstractions so vendor swaps are config changes
- **Async by default** — even fast Gemini calls go through Celery so the codepath matches Sjinn's slow path
