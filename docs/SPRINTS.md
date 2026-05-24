# Sprint Plan — img-vid-generation

> Last updated: 2026-05-24
> Current sprint: Sprints 0.5 → 5 **all complete end-to-end**. Sprint 4B (pgvector RAG) parked. Sprint 6 (Sjinn) is next.
> Stack: Next.js 16 (frontend), FastAPI (backend), monorepo via npm workspaces + uv
>
> **Completed sprints (with verification):**
> - Sprint 0.5 — Monorepo, FastAPI, Postgres+Alembic, OpenAPI codegen, Redis+Celery, dev orchestrator, READMEs.
> - Sprint 1.1 — Auth.js v5 + Google OAuth + HS256 JWS session strategy (jwt.encode/decode override in `apps/web/auth.ts`).
> - Sprint 1.2 — `users`, `profiles`, `credit_transactions` tables migrated to Supabase via Alembic.
> - Sprint 1.3 — FastAPI JWT verify middleware (`apps/api/app/deps/auth.py`), JIT user provisioning, drift refresh of name/avatar/sub.
> - Sprint 1.4 — `GET /me` endpoint with dev-email infinite-balance bypass.
> - Sprint 1.5 — Frontend `useMe()` hook + `/api/auth/token` HttpOnly-cookie relay + TanStack Query provider.
> - Sprint 1.6 — Shadcn/UI installed, `next-themes` system-preference dark mode, sticky navbar with credit badge + user menu, ADR-0012 written, system font stack (SF Pro on macOS).
> - Sprint 2 — Adapter pattern: `app/providers/{types,base,google_ai_studio}.py`, `gemini-2.5-flash` registered. `GET /models`, `POST /generations` (initial sync version), dynamic Zod form. Replaced with prompt-bar in 2.x polish (Shadcn pill, model dropdown, auto-resize textarea, system-font, "cursor-pointer" applied globally to Shadcn Button + DropdownMenuItem).
> - Sprint 3 — Async pipeline. `generations` table (status pending/processing/done/failed, prompt, result_text, result_url, cost_in_credits, error, timestamps). Celery task `run_generation` with credit deduction + refund-on-failure (uses generation_id as CreditTransaction reference_id — closes the Sprint 2 TODO). `POST /generations` enqueues + returns pending row; `GET /generations/{id}` for polling (owner-scoped 404); `GET /generations` list endpoint. Frontend `useGenerate` (mutation) + `useGeneration(id)` polling at 1Hz. `GenerationView` shows pending/processing/done/failed with bar pinned bottom; "← New generation" reset button.
> - Sprint 3.5 (ad-hoc, in-between) — Image generation cascade: `gemini-2.5-flash-image` registered (Nano Banana — currently quota-blocked on user's free tier with `limit: 0`) + `pollinations-flux` registered (PollinationsAdapter, stdlib urllib, **requires User-Agent + Referer headers to bypass Cloudflare bot detection**). Adapter routes text vs image responses by model_id substring "image". `result_url` widened to VARCHAR(10MB) to hold base64 data URIs. Frontend renders inline `<img>` for data:image URIs. ErrorCard now has friendly parser + collapsible "Show technical details".
> - Sprint 3.5.1 (2026-05-21) — Seegen.ai provider integration. Registered `seegen-gpt-image-2` (job-based: POST createTask → poll queryTask, adapter blocks internally to keep ProviderAdapter Protocol synchronous). Added `ModelConfig.enabled: bool = True` soft-disable switch — `gemini-2.5-flash-image` set to enabled=False (quota=0 on user's account). Default to 1k/medium resolution (~13 images per 200-credit free tier).
> - Sprint 4A.1 (2026-05-21) — R2 storage wired. `app/core/storage.py` (boto3 against R2's S3-compatible endpoint). Settings: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`, `R2_PUBLIC_URL`. Smoke test confirms upload + public-fetch + delete roundtrip. **Gotcha logged**: r2.dev public URLs 403 Python's default User-Agent (Cloudflare bot detection — same as Pollinations); browsers fine.
> - Sprint 4A.2 (2026-05-21) — Generation outputs migrated from base64 data URIs to R2. Celery task now decodes data:URIs OR server-side-fetches https URLs (with browser UA) and uploads to `generations/<id>.<ext>`. Alembic `2724c5210cfe` shrinks `result_url` back to VARCHAR(1024) (after NULL-ing legacy data:URI rows). Refund-on-storage-failure flagged as open business-logic question for Sprint 5 revisit.
> - Sprint 4A.3 + 4A.4 (2026-05-22) — Reference Library (image refs). Direct-upload via **presigned URLs** (browser → R2, not proxied through FastAPI). Three-step flow: `POST /references/presign` → browser `PUT` to R2 → `POST /references/{id}/complete` (backend HEADs R2 to verify before INSERT). CORS configured on bucket via `scripts/setup_r2_cors.py`. New `references` SQLModel + Alembic `352086a915a3`. Frontend: `useUploadReference` orchestrator hook, file picker in PromptBar with thumbnail strip + remove buttons, refs flow into `GenerationInput.image_urls`. Seegen adapter passes through `urls` array for image-to-image mode.
> - Sprint 4B (parked 2026-05-22) — pgvector RAG scaffold built then rolled back. No real use case for documents in an image-gen app. The five locked design decisions (single-table discriminator, separate chunks table, Gemini text-embedding-004, fixed-size chunking, retrieval injection in Celery task) preserved in this file's Sprint 4B section for future revisit when a real RAG use case appears.
> - Sprint 5 (2026-05-24) — Stripe credit packs. Backend: `app/billing/packs.py` catalog (3 packs: Starter $5/100c, Pro $20/500c, Studio $60/2000c), `/billing/packs` + `/billing/checkout` + `/webhooks/stripe` router. **Idempotency** via `UNIQUE (type, reference_id)` on credit_transactions (Alembic `a1e63fecb42b`) — Stripe webhook retries land as IntegrityError → 200 ack. Stripe-hosted Checkout (full redirect, hosted UI), webhook signature verification via `stripe.Webhook.construct_event` on raw bytes. Frontend: `BuyCreditsModal` (inline Tailwind overlay), `useBillingPacks` + `useStartCheckout` hooks, navbar credit pill is now clickable, `?checkout=success/cancel` return URL handler invalidates `["me"]` and strips params. Smoke-tested end-to-end with `stripe listen` and test card. New gotchas: `stripe.Event` doesn't support `.get()` (use bracket access), `whsec_` regenerates each `stripe listen` session.

## Architecture summary

Two services in a monorepo:
- `apps/web` — Next.js 16, Auth.js (JWT), TanStack Query, Shadcn/UI
- `apps/api` — FastAPI (Python 3.12), SQLModel, Alembic, Celery + Redis
- `packages/shared-types` — TS types generated from FastAPI's OpenAPI schema

Auth flow: Next.js handles Google OAuth via Auth.js, issues a JWT, includes it as `Authorization: Bearer ...` on every FastAPI call. FastAPI verifies the JWT using a shared secret.

## Decisions Log

| # | Decision | Choice | Date |
|---|----------|--------|------|
| D1 | AI provider (initial) | Gemini free models via Google AI Studio | 2026-04-28 |
| D2 | Premium video provider (later) | Sjinn (added in Sprint 6 — user does not have access yet) | 2026-04-28 |
| D3 | AI abstraction | Adapter pattern in `apps/api/app/providers/` | 2026-04-28 |
| D4 | Credits for dev/owner | Unlimited (hardcoded bypass for dev user by email) | 2026-04-28 |
| D5 | Free credits for new users | No by default; configurable via `FREE_STARTER_CREDITS` env var | 2026-04-28 |
| D6 | Stripe | Real implementation from Sprint 5 — no fake credits | 2026-04-28 |
| D7 | Auth provider (frontend) | Auth.js with Google OAuth, **JWT session strategy** | 2026-04-28 |
| D8 | Reference Library scope | **Path B (image + document RAG with pgvector)**, phased as Sprint 4A (R2 + image refs) then Sprint 4B (pgvector RAG). Prioritises learning depth over shipping speed. | 2026-05-21 |
| D9 | Storage & AI providers (dev) | R2 + Google AI Studio during dev (zero cost). GCS + Vertex AI later. | 2026-04-28 |
| D10 | ORM | ~~Drizzle~~ → **SQLModel + Alembic** (Python owns the DB now) | 2026-05-16 |
| D11 | Database (dev) | Supabase free Postgres via raw connection string | 2026-04-28 |
| D12 | Scaling architecture | Real job queue from Sprint 3 (Celery + Redis), not faked polling | 2026-05-16 |
| D13 | Backend topology | **Separate FastAPI service** (not Next.js Server Actions for business logic) | 2026-05-16 |
| D14 | Job queue | **Celery 5 + Redis** — industry standard, resume value | 2026-05-16 |
| D15 | Repo structure | Monorepo via npm workspaces; `apps/web`, `apps/api`, `packages/shared-types` | 2026-05-16 |
| D16 | Python runtime | Python 3.12 + uv + Ruff + mypy | 2026-05-16 |
| D17 | Cross-service contract | OpenAPI auto-generated by FastAPI, TS types generated via `openapi-typescript` | 2026-05-16 |
| D18 | Deployment target | PENDING — Vercel + Cloud Run vs full GCP vs Fly.io. Decided before Sprint 7. | - |

---

## Sprint 0.5 — Backend Foundation

**Goal:** Empty FastAPI service running locally alongside Next.js, with shared types flowing both ways.

### Tasks

#### 0.5.1 — Monorepo restructure
- Create `apps/web/` and move current Next.js code into it
- Create `apps/api/` for FastAPI
- Create `packages/shared-types/` placeholder
- Root `package.json` with npm workspaces
- Root `README.md` explaining the layout
- **Learn:** Monorepo structure with npm workspaces

#### 0.5.2 — FastAPI bootstrap
- Install Python 3.12 (pyenv or uv-managed)
- Initialize `apps/api/` with **uv** as package manager
- Add: fastapi, uvicorn, sqlmodel, alembic, pydantic, pydantic-settings
- Configure **Ruff** (linting + formatting) and **mypy** (type checking)
- Health endpoint: `GET /healthz` returns `{"status": "ok"}`
- **Learn:** Modern Python tooling — uv is ~10-100x faster than pip; Ruff replaces black/flake8/isort

#### 0.5.3 — Database connection
- SQLModel client connected to Supabase Postgres via `DATABASE_URL`
- Alembic initialized with first empty migration
- Test query: `SELECT 1` from a startup hook
- **Learn:** SQLModel = Pydantic models + SQLAlchemy mapping; Alembic migration workflow

#### 0.5.4 — OpenAPI codegen pipeline
- FastAPI auto-generates `/openapi.json`
- Script in `apps/web/`: `npm run gen:api-types` runs `openapi-typescript` against the FastAPI dev server
- Generated types land in `packages/shared-types/api.d.ts`
- **Learn:** This is the killer feature — type-safe Python ↔ TypeScript contracts for free

#### 0.5.5 — Redis (local Docker)
- `docker-compose.yml` at repo root: postgres-skip (we use Supabase), redis
- Celery installed in `apps/api/`, worker starts but has no tasks yet
- Confirm worker connects to local Redis
- **Learn:** Redis as message broker, Celery worker lifecycle

#### 0.5.6 — Dev workflow
- Root scripts: `npm run dev:web`, `npm run dev:api`, `npm run dev:worker`, `npm run dev` (runs all three)
- `.env.example` for each app
- **Learn:** Multi-process dev orchestration

#### 0.5.7 — Per-app READMEs
- Root `README.md` — project overview, setup instructions, link to docs/
- `apps/web/README.md` — frontend dev commands, env vars, type-gen workflow
- `apps/api/README.md` — uv commands, Alembic workflow, Celery worker, pytest, ruff/mypy
- **Learn:** Each readme is a contract — what a new contributor (or fresh Claude session) needs to operate that piece

**Sprint 0.5 done when:** You can `npm run dev`, see Next.js on `:3000`, FastAPI on `:8000`, Celery worker idle, and `apps/web` can import a generated type from `packages/shared-types`.

---

## Sprint 1 — Identity & Wallet

**Goal:** Log in via Google. Frontend and backend agree on who you are. Credit balance visible.

### Tasks

#### 1.1 — Auth.js with JWT session strategy
- Install `next-auth` v5 in `apps/web`
- Google OAuth provider
- **Session strategy: `jwt`** (not database) — see ADR-0009
- Shared `JWT_SECRET` env var (will also be used by FastAPI)
- Protect a test route
- **Learn:** OAuth 2.0 flow, JWT structure, why JWT vs DB sessions matters for service boundaries

#### 1.2 — Database schema (SQLModel)
- Define models: `User`, `Profile`, `CreditTransaction`
- Alembic migration: `001_initial_schema`
- Run migration against Supabase Postgres
- **Learn:** SQLModel field types, Alembic autogenerate vs manual migrations

#### 1.3 — FastAPI JWT middleware
- Dependency that extracts and verifies `Authorization: Bearer ...` using `JWT_SECRET`
- On first authenticated call: upsert `User` and `Profile` rows
- Dev user bypass: if `email == DEV_EMAIL`, balance presented as effectively infinite
- **Learn:** FastAPI dependencies, JWT verification, just-in-time user provisioning

#### 1.4 — `GET /me` endpoint
- Returns `{user, profile, balance}` for the authenticated user
- Pydantic response model → automatically reflected in OpenAPI
- **Learn:** Pydantic response models, FastAPI dependency injection

#### 1.5 — Frontend wiring
- `useMe()` TanStack Query hook calls `GET /me` with the JWT
- Sign-in / sign-out buttons via Auth.js
- **Learn:** TanStack Query setup, sending JWT from client to FastAPI

#### 1.6 — App shell with Credit Badge
- Shadcn/UI installation
- Navbar with logo, nav links, credit badge showing real balance, sign-in/out
- **Learn:** Shadcn/UI with Tailwind 4 CSS-native config (see GOTCHAS.md)

**Sprint 1 done when:** You sign in with Google, FastAPI provisions your user row, the navbar shows your balance.

---

## Sprint 2 — The Adaptive Model Layer (in FastAPI)

**Goal:** Config-driven AI generation. Same form, different models, zero special-casing.

### Tasks

#### 2.1 — Provider registry
- `apps/api/app/providers/__init__.py` exposes a registry dict
- `ModelConfig` Pydantic model with: `id`, `provider`, `display_name`, `input_types`, `cost_in_credits`, `is_async`
- First entry: Gemini 2.0 Flash via `google-generativeai`
- **Learn:** Python protocols / abstract base classes, registry pattern in a typed language

#### 2.2 — `GET /models` endpoint
- Returns the list of available `ModelConfig` entries
- **Learn:** How `GET /models` shapes the dynamic frontend form

#### 2.3 — `POST /generations` endpoint (synchronous path first)
- Accepts model_id + inputs, validates against the selected `ModelConfig`
- Calls the provider, returns the result
- Deducts credits via the ledger (or skips for dev user)
- **Learn:** Pydantic discriminated unions, transaction boundaries

#### 2.4 — Regenerate TS types
- Run `npm run gen:api-types` after the new endpoints land
- New types appear in `packages/shared-types`
- **Learn:** OpenAPI-to-TS contract regeneration as a dev habit

#### 2.5 — Dynamic generation form (Next.js)
- Reads `GET /models` to populate the model dropdown
- Renders form fields based on the selected model's `input_types`
- Zod schema built dynamically from the model config
- Submits to `POST /generations` with JWT
- **Learn:** Dynamic Zod schemas, generated-type-driven UI

**Sprint 2 done when:** You select a model, the form reshapes to its input requirements, you submit, and you see a Gemini-generated text result.

---

## Sprint 3 — Async Pipeline (DONE — R2 deliberately deferred)

**Goal as originally written:** Generations are persisted to R2 and run on Celery workers. Long jobs do not block HTTP requests.
**Actual scope:** Async pipeline + Celery worker + polling. **R2 deferred** because the only registered model at start of Sprint 3 was text-output (text gets stored in `result_text` column). R2 will land in Sprint 4 alongside reference uploads, or earlier if needed.

### What shipped

- ✅ **`generations` table** (`apps/api/app/models/generation.py`) — `id`, `user_id`, `model_id`, `prompt`, `status` (VARCHAR via `sa_column` trick, same as TransactionType), `result_text`, `result_url` (10MB), `error`, `cost_in_credits` (snapshot), timestamps. Alembic migration `1fc6b05d4ba6` + `a32c5a26fc53` (later widening for base64).
- ✅ **Celery task `run_generation`** (`apps/api/app/tasks/generation.py`) — idempotent (no-ops on terminal status); credit deduction with SELECT FOR UPDATE on profiles; auto-refund on provider failure; dev-user bypass.
- ✅ **POST `/generations` refactored to async** — returns 201 with pending row.
- ✅ **GET `/generations/{id}`** — owner-scoped (404 on foreign rows to avoid existence leak).
- ✅ **GET `/generations`** — paginated list (limit/offset), newest first.
- ✅ **Frontend `useGenerate`** — mutation that primes ["generation", id] cache; invalidates ["me"].
- ✅ **Frontend `useGeneration(id)`** — polls every 1s; stops at terminal status; invalidates ["me"] on terminal transition.
- ✅ **`GenerationView`** — empty (hero+centered bar) / inflight / done / failed states; "← New generation" reset button.

### Deferred to later

- 🔲 **R2 setup** — moves to Sprint 4 (Reference Library needs R2 for uploads anyway, so they bundle naturally). Image outputs currently use base64 data URIs as a stopgap.
- 🔲 **"My Generations" gallery UI** — the `GET /generations` endpoint exists; the visual history view does not. Easy add when needed.
- 🔲 **Retry policy with exponential backoff** — Celery's default retry behavior is in place; explicit policies wait for a real reliability need.

**Decision checkpoint after Sprint 3:** D8 — Reference Library scope (image-only vs RAG). Still pending.

---

## Sprint 3.5 — Image Generation Cascade (ad-hoc, between Sprint 3 and Sprint 4)

Tiny mini-sprint added because the app's whole purpose is image+video and Sprint 3 left it text-only.

### What 3.5 shipped

- ✅ Registered `gemini-2.5-flash-image` (Nano Banana) — output_type=IMAGE, cost=2. **Note: user's AI Studio free tier has `limit: 0` for this model.** Stays registered for when quota improves.
- ✅ Registered `pollinations-flux` — `PollinationsAdapter` (stdlib urllib, ~60 LOC). **Working** end-to-end with image rendering inline.
- ✅ Adapter routes by `"image" in model_id` substring; for image models it adds `response_modalities=["TEXT","IMAGE"]` to Gemini's config, parses `inline_data` from response parts, builds `data:{mime_type};base64,...` URI.
- ✅ Migration `a32c5a26fc53` widens `generations.result_url` to VARCHAR(10MB) for base64.
- ✅ `ResultCard` renders inline `<img>` when `result_url` starts with `data:image/` or has an image extension; falls back to `<a>` for arbitrary URLs.
- ✅ `ErrorCard` rewritten — `parseError()` maps common upstream errors (rate limit, provider unavailable, 403, 401, insufficient credits) to a friendly headline + suggestion; raw error under "Show technical details" toggle.
- ✅ "← New generation" reset button on the result view.

### 3.5 deferred (parked)

- 🔲 **Cloudflare Workers AI provider** — better-quality middle tier; user doesn't have a CF account yet. See parking lot.
- 🔲 **Migrate from `google.generativeai` to `google.genai`** — the SDK we use is deprecated in 2026; migration is a single-file change. Parked.

### 3.5.1 — Seegen.ai provider + soft-disable switch (2026-05-21)

- ✅ Registered `seegen-gpt-image-2` via new `SeegenAdapter` (`apps/api/app/providers/seegen.py`). **Job-based** API (`POST /jobs/createTask` → poll `/jobs/queryTask`); adapter blocks internally so the existing synchronous `ProviderAdapter` Protocol stays unchanged. 200 free credits at signup; ~5 test images at 2k/medium (35 of their credits each). Sprint 6's Sjinn integration will use the same job-based pattern, at which point we'll extend the Protocol with explicit `submit_async`/`poll_status` and have the Celery task re-enqueue itself between polls (vs the current "worker sleeps") — see ADR-0005 region.
- ✅ Added `ModelConfig.enabled: bool = True`. Disabled models stay registered (code intact) but are hidden from `GET /models` and rejected by `POST /generations` (404). Flipped `gemini-2.5-flash-image` to `enabled=False` — quota-blocked on user's account.

---

---

## Sprint 4 — Reference Library (D8 = Path B, phased)

D8 decided 2026-05-21: image refs **and** document RAG. Phased so each phase ships something usable rather than landing as one 2-sprint blob.

### Sprint 4A — R2 + image references (DONE — 2026-05-22)

**Ship checkpoint reached:** "upload cat photo + prompt 'edit this' → edited image via Seegen image-to-image."

- ✅ **4A.1** — R2 client wired (`app/core/storage.py`, boto3 against S3-compatible endpoint). Five env vars (`R2_ACCESS_KEY_ID/SECRET/ENDPOINT/BUCKET/PUBLIC_URL`). Smoke test confirms upload + public-fetch + delete. Gotcha: r2.dev URLs 403 Python's default UA — browser-side fine, server-side fetches must spoof a real UA.
- ✅ **4A.2** — Generation outputs migrated from data URIs to R2. Celery task decodes data URIs (Pollinations) or fetches https URLs (Seegen) with browser UA, uploads to `generations/<id>.<ext>`. Alembic `2724c5210cfe` shrinks `result_url` to VARCHAR(1024) after NULL-ing legacy data: rows.
- ✅ **4A.3** — Reference upload via **presigned PUT URLs** (direct browser → R2, not proxied through FastAPI). Three-step flow: `POST /references/presign` → browser `PUT` to R2 with bound Content-Type → `POST /references/{id}/complete` (backend HEADs R2 to verify size before INSERT). Bucket CORS configured via `scripts/setup_r2_cors.py`. `references` SQLModel + Alembic `352086a915a3`. Frontend: `useUploadReference` orchestrator, file picker + thumbnail strip in PromptBar, sequential upload of multi-file picks.
- ✅ **4A.4** — Refs flow into `GenerationInput.image_urls` from the frontend; Seegen adapter passes them through as the `urls` array (image-to-image mode). Other adapters (Pollinations, Gemini text) ignore `image_urls` — no special-casing.

### Sprint 4B — Document RAG (pgvector) — PARKED 2026-05-22

**Decision:** scope-cut. After scaffolding 4B.1 (pgvector extension + chunks table + HNSW index) we paused to re-examine the actual user story and found none — for an image-generation app, "references" are almost always *other images*, which 4A already handles. PDF/document uploads were a learning vehicle, not a product requirement.

Everything from 4B.1 was rolled back cleanly:

- Alembic downgraded → migration file deleted.
- `Reference` model reverted to its 4A.3 shape (no `kind`, no `extracted_text`).
- `pgvector` Python dep removed.
- `pgvector.*` mypy override removed.

The 5 locked architectural decisions (single-table discriminator, separate chunks table, Gemini text-embedding-004, fixed-size chunking, retrieval injection in the Celery task) are preserved here for if/when a real RAG use case appears — a "knowledge base" feature, a brand-style library, or a future document-Q&A pivot. Re-entering 4B from this design would take roughly the same effort whether started now or later, but **later** has the advantage of being driven by a concrete use case instead of "the obvious next thing in the plan."

Sprint 5 (Stripe + monetization) is now next.

---

## Sprint 5 — Monetization (DONE 2026-05-24)

**Shipped:** real Stripe. Credits backed by money. **Test-mode only** for now — live mode requires UAE entity setup (target market; deferred).

- ✅ **5.1 — Stripe Checkout.** `POST /billing/checkout` creates a `mode='payment'` Stripe Session with `client_reference_id = user.id`, returns the hosted URL. Browser does a full-page navigate to Stripe; `success_url`/`cancel_url` bounce back to `/?checkout=success|cancel`.
- ✅ **5.2 — Webhook with signature verification + idempotent ledger insert.** `POST /webhooks/stripe` reads RAW bytes (not parsed JSON — re-serialization breaks signature), passes them to `stripe.Webhook.construct_event(payload, sig, secret)`. On `checkout.session.completed` (only event we care about), fetches the session's line items to get `price_id`, looks up the pack via `app/billing/packs.py`, inserts `CreditTransaction(type=PURCHASE, reference_id=stripe_session_id, amount=credits)`. **Idempotency from the DB**: Alembic `a1e63fecb42b` adds `UNIQUE (type, reference_id)` on credit_transactions; a duplicate insert raises `IntegrityError` which we catch and ack with 200 so Stripe stops retrying.
- ✅ **5.3 — Buy Credits modal.** `BuyCreditsModal` (inline Tailwind overlay, no Shadcn Dialog dep) lists the three packs from `GET /billing/packs`. Navbar credit pill is now a button that opens the modal. `useStartCheckout` mutation creates the session and navigates the browser; `useCheckoutReturnHandler` (mounted in navbar) processes `?checkout=success` by invalidating the `["me"]` cache and stripping the params.
- ✅ **5.4 — Stripe CLI local dev workflow.** `stripe login` + `stripe listen --forward-to localhost:8000/webhooks/stripe`. The `whsec_...` printed is per-session — regenerates every restart of the listener (gotcha logged).

**Decisions made during this sprint:**

- One-off credit packs only — subscriptions deferred. The CreditTransaction ledger is already future-proof for subscription renewals (just adds a `SUBSCRIPTION_RENEWAL` enum value); no schema lock-in.
- Stripe-hosted Checkout (not embedded Elements). All card collection, 3DS, Apple Pay — on Stripe's domain. Future migration to Elements is localised to the frontend if we ever want fully embedded UI.
- Three SKUs: Starter ($5 / 100c), Pro ($20 / 500c), Studio ($60 / 2000c) — adjustable in Stripe dashboard; the catalog mirrors price + credit values in `app/billing/packs.py` keyed by Stripe price_id.
- Country = UAE in Stripe dashboard (target market; bypasses India invite-only restriction). Test-mode signup needs no verification — live-mode launch needs a real UAE entity OR a port to Razorpay.

**Still open (deferred to future):**

- Refund/dispute/chargeback handling — only `checkout.session.completed` handled today. Other events get 200 ack + no-op.
- Live-mode setup (real UAE entity, KYB, payouts) — Sprint 7 deployment concern.
- Refund-on-storage-failure policy (flagged in 4A.2) — left as-is for now; will revisit when real money is in the loop and the answer might change.

---

## Sprint 6 — Sjinn Integration

**Goal:** Premium video via the same form. Validates the registry pattern.

- 6.1: Sjinn provider added to `app/providers/`
- 6.2: Celery task with polling loop (Sjinn is task-based — submit, poll for status)
- 6.3: `cost_in_credits` differentiation per model (no special-casing)

---

## Sprint 7 — Deployment & Production (PENDING D18)

Options under consideration:
- Vercel (web) + Cloud Run (api + worker) + Cloud SQL + GCS + Vertex AI
- Full GCP for everything
- Fly.io for everything

To be decided before Sprint 7 begins.

---

## Open business-logic questions (flagged, not yet decided)

- **Refund-on-storage-failure (flagged 2026-05-21, Sprint 4A.2).** Currently, if the provider call succeeds but the R2 upload fails, we refund the user's credits and mark the row FAILED. Open question: is that the right policy? Provider compute *did* happen (we paid Seegen, we used Pollinations bandwidth), so a strict reading says credits should still be charged. Counter-argument: from the user's perspective they got no usable output, so refunding is the empathic call. Likely revisited around Sprint 5 (Stripe) when real money is in the loop. Also relevant: partial-success cases (Sjinn might produce a usable preview but fail final upload).

## Parking Lot

- **Migrate Gemini adapter from `google.generativeai` to `google.genai`.** The old SDK is deprecated as of 2026; current code works but should migrate before the deprecation becomes removal. Single-file change in `apps/api/app/providers/google_ai_studio.py`.

- **Image generation provider cascade.** When we add image generation (likely Sprint 3, once R2 storage exists; or pre-Sprint-3 with base64 data URIs), register three providers, all behind the existing `ProviderAdapter` protocol (ADR-0005):
  1. **Gemini 2.5 Flash Image** (`gemini-2.5-flash-image` aka "Nano Banana") — first try; reuses the existing API key + adapter, no new account. May hit `limit: 0` on free tier the way text did, in which case it stays registered but yields to the next provider.
  2. **Cloudflare Workers AI** — primary reliable free tier. ~25–100 images/day at 10k neurons. Needs CF account + API token. Models: FLUX.1-schnell, SDXL. New file: `apps/api/app/providers/cloudflare_workers_ai.py`.
  3. **Pollinations.ai** — fallback of last resort. No auth, URL-based (`https://image.pollinations.ai/prompt/{prompt}?model=flux`), FLUX-backed. Depends on a single org's goodwill — keep in pocket, don't rely on it.

  Pattern is a try-next-on-failure cascade at the `/generations` endpoint, not at the adapter layer. Failure modes: quota exhaustion (429), content blocked (4xx), provider unreachable (5xx, timeout). When all three fail, surface the failure.

- **Video generation.** Free-tier video gen does not realistically exist in 2026. Plan stays: Sjinn integration in Sprint 6. Until then, no video model is registered.

- **SSE for streaming text models (deliberate non-choice for Sprint 3).** Sprint 3 uses polling (`useGeneration` GETs `/generations/{id}` every 1s until terminal). For text models that support streaming (Gemini, GPT, Claude), Server-Sent Events would let tokens appear word-by-word like ChatGPT — meaningfully nicer UX. Implementation:
  - Backend: switch `model.generate_content()` to `stream=True`, return `StreamingResponse` with `text/event-stream` content type, yield `data: {"delta":"..."}` lines per token.
  - Frontend: use `fetch` with a `ReadableStream` reader (or `EventSource` for simpler cases); append deltas to local state.
  - ~3-4 hours of work. Coexists with polling — streaming models stream, atomic models (image, video) keep polling.
  - **Why we're not doing it in Sprint 3:** the polling pattern is what Sjinn and image/video gen need anyway. Validating it first is the right order. SSE is a UX polish layered on top, not an alternative architecture.

- Video timeline editor
- Public generation gallery / profiles
- Batch generations
- Cost analytics dashboard
- Mobile app (consuming the same FastAPI service — a real benefit of separate backend)
