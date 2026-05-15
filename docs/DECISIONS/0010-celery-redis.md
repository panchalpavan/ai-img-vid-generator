# ADR 0010: Celery + Redis for the job queue

**Status:** Accepted
**Date:** 2026-05-16

## Context

AI generation requests are not request/response — they range from a few seconds (Gemini text) to several minutes (Sjinn video). They must run outside the HTTP request cycle to avoid timeouts, allow retries, and survive deployments.

Options considered:

| Option | Vibe | Learning value | Operational cost |
|--------|------|----------------|------------------|
| **Celery + Redis** | Industry standard, heavy, used everywhere | High — concepts transfer | Higher — worker process, broker, beat scheduler |
| **arq** | Modern, async-native, simpler | Medium — clean but niche | Low |
| **Dramatiq** | Lighter Celery alternative | Medium | Low |
| **Inngest / Trigger.dev** | Hosted, durable | Low — mechanics hidden | Zero |
| **FastAPI BackgroundTasks** | In-process, no queue | None — toy only | Zero but lost on restart |

## Decision

Use **Celery 5 with Redis as the broker and result backend**.

Configuration:
- Redis runs locally in Docker during development (`docker-compose.yml` at repo root)
- Single Celery worker process during development (`celery -A app.tasks worker`)
- Celery Beat for any future scheduled tasks (cleanup, expired-token cleanup, etc.)
- Tasks live in `apps/api/app/tasks/`
- Result backend: Redis (used for status polling fallback; primary source of truth is the `generations` table in Postgres)

## Consequences

**Positive:**
- Celery is *the* Python job framework — concepts (broker, workers, beat, exchanges, retries, idempotency) are universally applicable
- Retries with exponential backoff are first-class
- Horizontal scaling is configuration: spawn more workers, done
- Redis introduces a third infrastructure primitive the user explicitly wanted to learn (in addition to Postgres and object storage)
- Same Redis instance is reused for:
  - Celery broker (queueing)
  - Celery result backend (task state)
  - Future cache layer (rate limits, model config, etc.)
  - Future JWT blacklist (ADR-0009 mitigation)
- Skills transfer to any Python backend job in the market

**Negative:**
- More moving parts than `arq`. There's a real Celery config file, a worker process to manage, and a vocabulary to learn (acks, prefetch, eager mode).
- Celery's docs are sprawling — easy to over-engineer early.
- In production, Redis becomes a hard dependency that must be operated (managed service like Upstash / Memorystore).

## Alternatives considered

- **arq.** Genuinely the nicer DX choice in 2026 — async-native, smaller surface area, "Celery for the modern era." Rejected because the user wants resume-recognized skills. arq jobs do not show up in job descriptions yet; Celery does.
- **Inngest.** Excellent product. Rejected because it abstracts away the job-queue mechanics the user wants to learn.
- **FastAPI BackgroundTasks.** Rejected outright — tasks die with the process. Fine for fire-and-forget logging, not for AI jobs.

## Implementation notes

- All generation tasks must be **idempotent** — keyed on `generation_id`. A retry must not duplicate side effects.
- Result URLs in R2 should use `generation_id` as part of the key so retries overwrite the same object rather than creating orphans.
- Eager mode (`task_always_eager=True`) is used in tests to run tasks synchronously.
- Future: when generations exceed minutes (Sjinn video), consider moving long polling loops into Celery tasks that re-enqueue themselves (chain) rather than blocking a worker.
