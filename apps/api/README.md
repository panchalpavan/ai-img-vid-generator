# apps/api — FastAPI backend

> **Status:** This directory is the monorepo placement for the backend. The actual FastAPI bootstrap happens in Sprint 0.5.2.

The backend owns the database, AI orchestration, jobs, webhooks, and business logic. The frontend (`apps/web`) calls this service over HTTPS with a JWT issued by Auth.js.

## Tooling

- **Python 3.12**
- **uv** — package manager (replaces pip/poetry; ~10-100x faster). See `pyproject.toml`.
- **Ruff** — linting + formatting (replaces black, flake8, isort)
- **mypy** — type checking
- **FastAPI** — web framework
- **SQLModel + Alembic** — ORM and migrations
- **Celery + Redis** — job queue
- **pytest + httpx** — testing

## Commands

Once Sprint 0.5.2 is complete, these will work:

```bash
# From this folder:
uv sync                    # Install dependencies
uv run uvicorn app.main:app --reload    # Dev server on :8000
uv run celery -A app.tasks worker --loglevel=info   # Celery worker
uv run alembic upgrade head             # Apply DB migrations
uv run alembic revision --autogenerate -m "message"  # New migration
uv run ruff check .         # Lint
uv run ruff format .        # Format
uv run mypy .               # Type check
uv run pytest               # Tests

# From the monorepo root:
npm run dev:api             # Same as uvicorn above, wrapped
npm run dev:worker          # Celery worker
```

## Environment variables

Create `apps/api/.env` (gitignored). See `.env.example` once it exists.

| Variable | Purpose | When added |
|----------|---------|------------|
| `DATABASE_URL` | Supabase Postgres connection string | Sprint 0.5.3 |
| `JWT_SECRET` | Shared with `apps/web` for JWT verification | Sprint 1.3 |
| `REDIS_URL` | Celery broker + result backend | Sprint 0.5.5 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_ENDPOINT` / `R2_BUCKET` | Cloudflare R2 | Sprint 3.1 |
| `GOOGLE_API_KEY` | Google AI Studio (Gemini) | Sprint 2.3 |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe | Sprint 5 |
| `DEV_EMAIL` | Email of the dev user (unlimited credits bypass) | Sprint 1.3 |
| `FREE_STARTER_CREDITS` | New user starting balance (default 0) | Sprint 1.3 |

## Folder layout (planned)

```
apps/api/
├── app/
│   ├── main.py           # FastAPI app instance
│   ├── core/             # Config (Pydantic Settings), security, lifespan hooks
│   ├── deps/             # FastAPI dependencies (DB session, current user)
│   ├── routers/          # HTTP routes grouped by resource
│   ├── models/           # SQLModel table definitions
│   ├── schemas/          # Pydantic request/response schemas (non-table)
│   ├── providers/        # AI provider adapters (Gemini, Sjinn) — ADR-0005
│   ├── storage/          # R2/S3 abstraction
│   └── tasks/            # Celery tasks
├── alembic/              # Migration scripts
├── tests/                # pytest
├── pyproject.toml        # uv-managed deps and tool config
└── uv.lock               # Lockfile (committed)
```

## Architecture context

- All endpoints are protected by JWT verification except `/healthz` and `/webhooks/*`.
- Webhooks (Stripe) verify a different signature (HMAC) and bypass user JWT auth.
- Long-running jobs go through Celery, never inline in HTTP handlers (ADR-0010).
- See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) and [docs/DECISIONS/](../../docs/DECISIONS/).
