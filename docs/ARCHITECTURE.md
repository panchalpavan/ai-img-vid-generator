# Architecture

## Stack (locked as of 2026-04-28)

### Application

| Layer | Technology | Notes |
|-------|------------|-------|
| Framework | Next.js (App Router) | 16.2.4 — breaking changes from prior versions, read `node_modules/next/dist/docs/` before writing code |
| UI | React | 19.2.4 |
| Language | TypeScript (strict) | ^5 |
| Styling | Tailwind CSS | ^4 (CSS-native config, no `tailwind.config.js`) |
| Component lib | Shadcn/UI | Added in Sprint 1 |
| Data fetching (client) | TanStack Query | Added in Sprint 3 |
| Package manager | npm | Always npm — never pnpm/yarn/bun |

### Backend (development — zero cost)

| Layer | Technology | Notes |
|-------|------------|-------|
| Auth | Auth.js (next-auth v5) | Google OAuth provider. ADR-0001 |
| ORM | Drizzle ORM | Raw SQL output, no cold-start penalty. ADR-0002 |
| Database | Supabase free Postgres | Connection string only, NOT Supabase JS client. ADR-0003 |
| Storage | Cloudflare R2 | 10GB free, no egress fees. ADR-0004 |
| AI (Gemini) | Google AI Studio | Free tier, rate-limited. ADR-0004 |
| AI (premium video) | Sjinn | Added in Sprint 6 — user does not have access yet |
| Hosting | Vercel | Free tier sufficient for dev |

### Backend (Sprint 7 production — migrates to GCP)

| Layer | Migration target | Reason |
|-------|------------------|--------|
| Database | Cloud SQL (PostgreSQL) | Swap `DATABASE_URL` only — Drizzle code unchanged |
| Storage | Cloud Storage (GCS) | Swap S3 client config |
| AI (Gemini) | Vertex AI | Same models, GCP-native billing, better quota |
| Hosting | Cloud Run | Container deployment, long-running support |

All Sprint 7 swaps are **config changes, not code rewrites** — this is enforced by the adapter pattern (ADR-0005).

## File structure

```
app/
  layout.tsx          # Root layout — fonts, providers, html shell
  page.tsx            # Home page (Server Component)
  globals.css         # Tailwind CSS 4 base + design tokens
  (auth)/             # Auth.js routes (Sprint 1)
  (app)/              # Authenticated app routes (Sprint 1+)
  api/                # API routes (webhooks, status endpoints)
components/
  ui/                 # Shadcn/UI primitives
  *                   # Domain components
lib/
  db/                 # Drizzle schema, client, migrations
  auth/               # Auth.js config
  models.ts           # AI model registry (adapter pattern — ADR-0005)
  storage/            # R2/GCS abstraction
public/               # Static assets served at /
docs/
  ARCHITECTURE.md     # This file — locked stack and structure
  CONVENTIONS.md      # Code style and naming rules
  GOTCHAS.md          # Next.js 16 / Tailwind 4 / React 19 sharp edges
  SPRINTS.md          # Sprint plan and decisions log
  DECISIONS/          # ADRs — one file per significant decision
.claude/              # Claude Code agents, skills, hooks, settings
```

## Key architectural principles

1. **App Router only** — no Pages Router. All routing under `app/`.
2. **Server Components by default** — add `"use client"` at the lowest possible boundary.
3. **Tailwind CSS 4 is CSS-native** — design tokens in `app/globals.css` via `@theme` and CSS variables. No `tailwind.config.js`.
4. **No proprietary clients where a portable alternative exists** — no Supabase JS client, no Firebase SDK. Use raw connection strings + open-source libs (Drizzle, Auth.js).
5. **Adapter pattern for external providers** — AI, storage, and DB all sit behind thin abstractions (`lib/models.ts`, `lib/storage/*`, Drizzle). Migration is env-var-only.
6. **Async pipeline is the default** — even fast Gemini calls go through the same `pending → processing → done` flow that Sjinn requires. No special-casing sync vs async.
7. **Credit ledger, not mutable balance** — every credit movement inserts a `credit_transactions` row. Balance is derived. ADR-0006.

## Data flow

### Synchronous (Gemini text/image — fast)

```
Browser
  → Next.js Server Action (validates input, checks credits)
  → AI model registry (lib/models.ts) → resolves to Gemini adapter
  → Google AI Studio API
  → Result saved to R2 + DB (generations table, status=done)
  → Response to browser
```

### Asynchronous (Sjinn video — slow)

```
Browser
  → Next.js Server Action (validates input, checks credits)
  → Creates `generations` row (status=pending)
  → Submits job to Sjinn → returns task ID
  → Browser polls /api/generations/[id]/status
  → Polling endpoint checks Sjinn task status
  → On done: stores result in R2, updates DB (status=done)
  → Browser receives final result
```

### Payment

```
Browser
  → Stripe Checkout (hosted)
  → Stripe redirects to success URL
  → Stripe webhook POSTs to /api/webhooks/stripe (signature verified)
  → Insert `credit_transactions` row (type=credit)
  → Balance reflected on next read
```

## Scaling path (not built yet, designed for)

Current architecture sustains low-millions of SaaS users when these are added:

- **Connection pooler** in front of Postgres (PgBouncer / Supavisor / Neon's pooler)
- **Job queue** (BullMQ + Redis, or Cloud Tasks) replacing inline async polling
- **Worker service** on Cloud Run for heavy/long jobs (offloaded from Next.js Server Actions)
- **CDN caching** for R2/GCS public URLs (Cloudflare or Cloud CDN)

Sprint 3's async polling pattern is the foundation — swapping it for a real queue does not require touching the UI or model registry.

## Adding new routes

Create a folder under `app/` with a `page.tsx`. Layouts cascade automatically. Loading and error states go in `loading.tsx` and `error.tsx` siblings.
