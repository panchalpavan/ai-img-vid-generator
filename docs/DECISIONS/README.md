# Architecture Decision Records (ADRs)

This folder records significant architectural decisions with context and trade-offs. New ADRs are added when:
- A new npm dependency is introduced (per CLAUDE.md rule)
- A vendor or provider is chosen
- A pattern is adopted that future contributors should not silently revisit

## Index

| # | Title | Status | Date |
|---|-------|--------|------|
| 0001 | Auth.js over Supabase Auth and Firebase Auth | Accepted | 2026-04-28 |
| 0002 | Drizzle ORM over Prisma | Accepted | 2026-04-28 |
| 0003 | Supabase free Postgres for development | Accepted | 2026-04-28 |
| 0004 | Cloudflare R2 and Google AI Studio for development | Accepted | 2026-04-28 |
| 0005 | Adapter pattern for AI providers | Accepted | 2026-04-28 |
| 0006 | Credit ledger over mutable balance | Accepted | 2026-04-28 |

## Format

Each ADR is a short markdown file. Sections: **Context**, **Decision**, **Consequences**, **Alternatives considered**.
