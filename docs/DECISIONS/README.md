# Architecture Decision Records (ADRs)

This folder records significant architectural decisions with context and trade-offs. New ADRs are added when:
- A new npm or pip dependency is introduced
- A vendor or provider is chosen
- A pattern is adopted that future contributors should not silently revisit

## Index

| # | Title | Status | Date |
|---|-------|--------|------|
| 0001 | Auth.js over Supabase Auth and Firebase Auth | Accepted | 2026-04-28 |
| 0002 | ~~Drizzle ORM over Prisma~~ | **Superseded by ADR-0008** | 2026-04-28 |
| 0003 | Supabase free Postgres for development | Accepted | 2026-04-28 |
| 0004 | Cloudflare R2 and Google AI Studio for development | Accepted | 2026-04-28 |
| 0005 | Adapter pattern for AI providers | Accepted (relocated to FastAPI per ADR-0007) | 2026-04-28 |
| 0006 | Credit ledger over mutable balance | Accepted | 2026-04-28 |
| 0007 | FastAPI as a separate backend service | Accepted | 2026-05-16 |
| 0008 | SQLModel + Alembic over Drizzle | Accepted | 2026-05-16 |
| 0009 | JWT-based auth between Next.js and FastAPI | Accepted | 2026-05-16 |
| 0010 | Celery + Redis for the job queue | Accepted | 2026-05-16 |
| 0011 | Monorepo via npm workspaces + uv | Accepted | 2026-05-16 |

## Format

Each ADR is a short markdown file. Sections: **Context**, **Decision**, **Consequences**, **Alternatives considered**.
