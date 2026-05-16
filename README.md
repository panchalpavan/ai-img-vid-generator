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
# Prerequisites: Docker Desktop, Node 20+, uv (https://docs.astral.sh/uv/)

# 1. Install JS dependencies (apps/web + packages/*)
npm install

# 2. Install Python dependencies + create virtualenv
uv --directory apps/api sync

# 3. Copy example env file and fill in your Supabase + Redis URLs
cp apps/api/.env.example apps/api/.env
$EDITOR apps/api/.env

# 4. Apply DB migrations
uv --directory apps/api run alembic upgrade head

# 5. Start everything (Redis auto-starts via predev hook):
npm run dev
# → Next.js  on http://localhost:3000
# → FastAPI  on http://localhost:8000  (docs at /docs)
# → Celery worker (background)
# → Redis    on host port 6380 (Docker)

# Or run any of them individually:
npm run dev:web | dev:api | dev:worker

# Other useful scripts:
npm run gen:api-types     # Regenerate TS types from FastAPI's OpenAPI schema
npm run lint              # Lint web + api
npm run build:web         # Production build of Next.js
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
