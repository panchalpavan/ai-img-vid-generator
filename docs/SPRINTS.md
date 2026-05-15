# Sprint Plan — img-vid-generation

> Last updated: 2026-04-28
> Current sprint: Not started (pending Sprint 1 auth decision)
> Stack: Next.js 16, React 19, TypeScript, Tailwind CSS 4, App Router

## Decisions Log

| # | Decision | Choice | Date |
|---|----------|--------|------|
| D1 | AI provider (initial) | Gemini free models via Google AI Studio | 2026-04-28 |
| D2 | Premium video provider (later) | Sjinn (provisioned in Sprint 6, not yet accessed) | 2026-04-28 |
| D3 | AI abstraction | Adapter pattern via `lib/models.ts` registry | 2026-04-28 |
| D4 | Credits for dev/owner | Unlimited (hardcoded bypass for dev user) | 2026-04-28 |
| D5 | Free credits for new users | **No** by default — configurable via env flag `FREE_STARTER_CREDITS` (0 = off) | 2026-04-28 |
| D6 | Stripe | Real implementation, no fake/mock credits | 2026-04-28 |
| D7 | Auth provider | **Auth.js with Google OAuth** (no Firebase, no Supabase Auth — portable) | 2026-04-28 |
| D8 | Reference Library scope | **PENDING** — image-only vs document RAG (pgvector) | - |
| D9 | Storage & AI providers (dev) | **R2 + Google AI Studio** during dev (zero cost). Migrate to GCS + Vertex AI in Sprint 7. | 2026-04-28 |
| D10 | ORM | **Drizzle ORM** — lightweight, raw SQL, no cold-start penalty, scales | 2026-04-28 |
| D11 | Database (dev) | **Supabase free Postgres** via connection string (not Supabase client). Migrate to Cloud SQL in Sprint 7. | 2026-04-28 |
| D12 | Scaling architecture | Build async pattern in Sprint 3 as foundation; introduce job queue (BullMQ/Cloud Tasks) only when traffic demands it | 2026-04-28 |

---

## Sprint 1 — Identity & Wallet

**Goal:** A user can log in and see their credit balance. Nothing generates yet.
**Prerequisite:** Decision D7 (auth provider) must be made first.

### Tasks

#### 1.1 — Auth Setup
- Configure chosen auth provider (Auth.js or Supabase Auth) with Google OAuth
- Set up environment variables (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc.)
- Protect a test route — confirm session works end-to-end
- **Learn:** OAuth 2.0 flow, Next.js middleware for route protection

#### 1.2 — Database Schema & User Profile
- Set up DB client (Drizzle ORM or Supabase client — depends on D7)
- Create `profiles` table: `id`, `user_id` (FK to auth), `credit_balance`, `created_at`
- Create `credit_transactions` table: `id`, `user_id`, `amount`, `type` (credit/debit), `reason`, `created_at`
- Add DB trigger or Server Action that auto-creates a `profiles` row on first login
- Dev bypass: if `user.email === process.env.DEV_EMAIL`, balance reads as `Infinity` (or a very large number)
- **Learn:** PostgreSQL triggers vs application-level hooks, why transactions > direct balance mutation

#### 1.3 — Credit Reading (Server Action / Hook)
- `getCredits(userId)` Server Action — reads balance from DB
- `useCredits()` client hook that calls it
- **Learn:** Server Actions data flow, when to use Server Components vs Client Components for data

#### 1.4 — App Shell & Credit Badge
- Install Shadcn/UI, configure with Tailwind 4
- Build navbar with: logo, nav links, Credit Badge (real balance), sign-in/sign-out button
- Credit Badge updates on route change (not real-time yet)
- **Learn:** Shadcn/UI setup with Tailwind 4 CSS-native config (no tailwind.config.js — see GOTCHAS.md)

**Sprint 1 done when:** You can log in with Google, see a credit balance in the navbar, and sign out.

---

## Sprint 2 — The Adaptive Model Layer

**Goal:** A config-driven form that knows nothing about specific AI providers. Swap models via config, not code.

### Tasks

#### 2.1 — Model Registry (`lib/models.ts`)
- Define `ModelConfig` TypeScript type with: `id`, `provider`, `name`, `inputTypes` (`text` | `image` | `video`), `costPerCredit`, `isAsync`
- Add first entry: Gemini 2.0 Flash (provider: `google`, inputTypes: `['text']`, isAsync: false)
- **Learn:** TypeScript discriminated unions, config-as-code, why this makes Sprint 6 a 10-line change

#### 2.2 — Dynamic Generation Form
- Form component reads `inputTypes` from a selected `ModelConfig`
- If config includes `text` → render Textarea
- If config includes `image` → render File Uploader
- Validation via Zod — schema is built dynamically from the config
- **Learn:** Dynamic Zod schemas, controlled forms, `"use client"` boundary decisions

#### 2.3 — Gemini Integration (Server Action)
- Server Action: receives validated form data + selected model id
- Looks up model config, calls the right provider (Gemini for now)
- Returns the generated text/image result
- Deducts credits (or skips deduction for dev user)
- **Learn:** Google Generative AI SDK, Server Action error handling, credit deduction pattern

**Sprint 2 done when:** You can type a prompt, submit, and see a Gemini-generated result on screen. Switching the model dropdown changes which inputs are shown.

---

## Sprint 3 — Files, Storage & Async Results

**Goal:** Generated output is persisted. Long-running tasks (video generation) don't block the UI.

### Tasks

#### 3.1 — Cloudflare R2 Setup
- Create R2 bucket, configure S3-compatible client in Next.js
- `uploadToR2(buffer, key)` utility — returns public URL
- Add ADR: why R2 over Supabase Storage (see `docs/DECISIONS/`)
- **Learn:** Object storage, presigned URLs, environment secrets management

#### 3.2 — Generations Table
- Create `generations` table: `id`, `user_id`, `model_id`, `prompt`, `status` (`pending` | `processing` | `done` | `failed`), `result_url`, `created_at`
- **Learn:** Status state machines, why `pending` and `processing` are different states

#### 3.3 — Async Result Pattern
- On generation submit: create `pending` row → kick off job → poll `GET /api/generations/[id]/status`
- Update row to `done` + store R2 URL when complete
- This pattern works for Gemini (fast) and Sjinn (slow) — same code, different latency
- **Learn:** Polling vs webhooks, optimistic UI, why you design for async even when sync is available

#### 3.4 — "My Generations" Gallery
- Grid view of all user generations with status badges
- TanStack Query for fetching — cache invalidation on new generation
- **Learn:** TanStack Query setup in Next.js App Router, stale-while-revalidate pattern

**Sprint 3 done when:** Generated images/text are saved to R2 and appear in a gallery. A "pending" spinner shows while the job runs.

**Decision checkpoint after Sprint 3:**
> **Reference Library scope (D8):**
> - **Path A — Image-only:** Pass uploaded image directly as model input. No new infrastructure. Sprint 4 adds ~2 tasks.
> - **Path B — Document RAG:** Add pgvector to Postgres, pick embedding model, build retrieval step. Adds ~1.5 extra sprints of work.

---

## Sprint 4 — Reference Library

**Goal:** Users upload a reference (image and/or doc) that shapes the generation.
**Scope depends on D8 decision.**

### Tasks

#### 4.1 — Reference Upload UI
- Drag-and-drop uploader → uploads to R2, shows preview
- **Learn:** File handling, multipart upload, client-side image preview

#### 4.2 — Reference-Aware Generation (Path A — image-only)
- Pass R2 image URL as multimodal context to the model
- Update `ModelConfig` to indicate which models support `imageContext`
- **Learn:** Multimodal API calls, base64 vs URL image passing

#### 4.3 — *(Path B only)* pgvector + Embedding Pipeline
- Enable pgvector extension on Postgres
- On upload: embed the document via Gemini embedding model → store vector
- On generation: retrieve top-k similar chunks → inject into prompt
- **Learn:** RAG architecture, vector similarity search, embedding models

#### 4.4 — Reference Library Management
- `references` table: `id`, `user_id`, `name`, `r2_url`, `type`, `created_at`
- UI to name, list, and delete saved references
- **Learn:** CRUD with ownership scoping (only see your own references)

**Sprint 4 done when:** You can upload an image, select it as context, and the generation visibly reflects it.

---

## Sprint 5 — Monetization

**Goal:** Credits are real money. Every purchase and spend is audited.

### Tasks

#### 5.1 — Stripe Checkout
- "Buy Credits" modal with credit packages (e.g. 10 / 50 / 100 credits)
- Stripe Checkout session → hosted payment page
- **Learn:** Stripe SDK, checkout session creation, idempotency keys

#### 5.2 — Stripe Webhook Handler (`/api/webhooks/stripe`)
- Verify Stripe signature on every request (critical — never skip this)
- On `checkout.session.completed`: increment `credit_balance`, insert `credit_transactions` row
- **Learn:** Webhook security, why signature verification is non-negotiable, raw body parsing

#### 5.3 — Transaction Ledger
- Every generation deducts from `credit_transactions` (never mutate balance directly)
- Balance is always `SUM(credit_transactions)` or a cached denormalization
- **Learn:** Ledger pattern vs mutable balance, audit trails

**Sprint 5 done when:** You can buy credits with a real Stripe test card and see the balance update in the navbar.

---

## Sprint 6 — Sjinn Integration

**Goal:** Add premium video generation behind the same form. Validates the adapter pattern from Sprint 2.

### Tasks

#### 6.1 — Sjinn Model Config Entry
- Add Sjinn models to `lib/models.ts` (Veo3, Kling, etc.)
- No form changes, no pipeline changes — just config
- **Learn:** This is the payoff of Sprint 2's design

#### 6.2 — Sjinn Polling Loop
- Sjinn jobs are async: submit → get task ID → poll until `status === "done"`
- Implement exponential backoff in the polling loop
- Reuses the async pattern from Sprint 3.3
- **Learn:** Long-polling, exponential backoff, job queue mental model

#### 6.3 — Credit Cost Differentiation
- Sjinn tasks cost more credits than Gemini tasks
- `costPerCredit` from `ModelConfig` drives deduction — no special-casing
- **Learn:** How config-driven cost avoids if/else spaghetti

**Sprint 6 done when:** You can generate a video via Sjinn using the same form as Gemini, paying the right credit cost.

---

## Sprint 7 — Production & DevOps (Optional)

**Goal:** Ship it publicly.

- GCP Cloud Run for generation Server Action (offload from Next.js serverless)
- PWA: `manifest.json`, service worker, offline shell
- Production Supabase / Neon, production Stripe, production R2
- Environment management: `dev` / `staging` / `prod`

---

## Parking Lot (future ideas, not scheduled)

- Video timeline editor (Canvas-based)
- Shared generation gallery (public profiles)
- Batch generation jobs
- Cost analytics dashboard
- Model comparison A/B view
