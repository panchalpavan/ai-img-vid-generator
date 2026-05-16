# apps/api — FastAPI backend

The backend owns the database, AI orchestration, jobs, webhooks, and business logic. The frontend (`apps/web`) calls this service over HTTPS with a JWT issued by Auth.js (Sprint 1.1+).

## Tooling

- **Python 3.12** — managed via `.python-version`
- **uv** — package manager + virtualenv (replaces pip / poetry / pyenv)
- **Ruff** — linter + formatter (replaces black + flake8 + isort)
- **mypy** — strict type checking
- **FastAPI** — web framework
- **SQLModel + Alembic** — ORM and migrations
- **Celery + Redis** — job queue (local Redis runs in Docker via repo-root `docker-compose.yml`)
- **pytest + httpx** — testing

## Commands

Run these from this folder, OR use the equivalents in the repo-root `package.json` (e.g., `npm run dev:api`).

```bash
uv sync                                  # Install / refresh dependencies
uv run uvicorn app.main:app --reload     # Dev server on :8000
uv run celery -A app.tasks worker        # Celery worker
uv run alembic upgrade head              # Apply DB migrations
uv run alembic revision -m "msg"         # Create empty migration
uv run alembic revision --autogenerate -m "msg"  # Create migration from model diff
uv run ruff check .                      # Lint
uv run ruff format .                     # Format
uv run mypy app                          # Type check
uv run pytest                            # Tests
uv run python -m app.openapi_export      # Dump OpenAPI schema to stdout
```

From repo root:

```bash
npm run dev:api                          # uvicorn (auto-reload)
npm run dev:worker                       # Celery worker
npm run lint:api / format:api / typecheck:api / test:api
npm run gen:api-types                    # Dump schema + regenerate TS types in packages/shared-types
```

## Environment variables

Copy `.env.example` to `.env` and fill in real values. `.env` is gitignored.

| Variable | Purpose | Sprint added |
|----------|---------|--------------|
| `DATABASE_URL` | Postgres connection (use Supabase **pooler** URL — see `.env.example` for the gotcha) | 0.5.3 |
| `REDIS_URL` | Celery broker + result backend (local Docker on port 6380) | 0.5.5 |
| `JWT_SECRET` | Shared with `apps/web` for JWT verification | 1.3 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_ENDPOINT` / `R2_BUCKET` | Cloudflare R2 | 3.1 |
| `GOOGLE_API_KEY` | Google AI Studio (Gemini) | 2.3 |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe | 5 |
| `DEV_EMAIL` | Email of the dev user (unlimited credits bypass) | 1.3 |
| `FREE_STARTER_CREDITS` | New user starting balance (default 0) | 1.3 |

## Folder layout

```
apps/api/
├── app/
│   ├── main.py           # FastAPI app + health endpoints
│   ├── core/             # Config (Pydantic Settings), DB engine
│   ├── tasks/            # Celery app + tasks (ping for now)
│   ├── openapi_export.py # Dumps OpenAPI schema to stdout for TS codegen
│   ├── deps/             # FastAPI dependencies (Sprint 1+)
│   ├── routers/          # HTTP routes grouped by resource (Sprint 1+)
│   ├── models/           # SQLModel table definitions (Sprint 1.2+)
│   ├── schemas/          # Pydantic request/response schemas (Sprint 1+)
│   ├── providers/        # AI provider adapters (Sprint 2+)
│   └── storage/          # R2/S3 abstraction (Sprint 3+)
├── alembic/              # Migration scripts (env.py reads DATABASE_URL from Settings)
├── tests/                # pytest + conftest.py (sets dummy env for imports)
├── pyproject.toml        # uv-managed deps + Ruff/mypy/pytest config
└── uv.lock               # Lockfile (committed)
```

## Architecture context

- All endpoints will be protected by JWT verification once auth lands (Sprint 1.3), except `/healthz`, `/healthz/db`, and `/webhooks/*`.
- Webhooks (Stripe) verify their own HMAC signature and bypass user JWT auth.
- Long-running jobs run on Celery workers, never inline in HTTP handlers (ADR-0010).
- See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) and [docs/DECISIONS/](../../docs/DECISIONS/).
