# ADR 0004: Cloudflare R2 and Google AI Studio for development

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app needs object storage and an AI provider during development at zero cost.

**Storage options:**
- Cloudflare R2 — 10GB free, no egress fees, hard $0 spend cap
- Cloud Storage (GCS) — 5GB free tier (us-only regions), requires billing setup with a card, can charge silently past limits
- Supabase Storage — included in Supabase free tier but uses the proprietary client

**AI options:**
- Google AI Studio — free Gemini access, rate-limited
- Vertex AI — same Gemini models but requires GCP billing setup, not free
- OpenAI API — paid

## Decision

For development:
- **Storage:** Cloudflare R2 via S3-compatible client (`@aws-sdk/client-s3`)
- **AI:** Google AI Studio via `@google/generative-ai` SDK

Both sit behind adapters (`lib/storage/*` and `lib/models.ts`) so Sprint 7 can swap to GCS and Vertex AI by changing config, not code.

## Consequences

**Positive:**
- Truly zero cost during development
- R2 is S3-compatible — swapping to GCS later is a client-config change
- Google AI Studio uses the same Gemini model family as Vertex AI — prompts and behavior are identical, only the SDK differs

**Negative:**
- Two vendors during development (Cloudflare for storage, Google for AI) — slightly more setup
- Google AI Studio rate limits are tight (15 RPM on free Gemini Flash) — fine for dev, not for users at scale
- Sprint 7 has a migration to do (R2 → GCS, AI Studio → Vertex AI)

## Alternatives considered

- **Full GCP from day one (GCS + Vertex AI):** Rejected — requires billing setup, Cloud SQL is ~$7/mo minimum, and silent charge risk on GCS past 5GB. User explicitly wants zero dev spend.
- **Supabase Storage:** Rejected because it pulls in the Supabase JS client, contradicting ADR-0001's stance on portable abstractions.
