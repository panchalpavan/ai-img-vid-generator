# apps/web — Next.js frontend

The user-facing application. Handles UI, authentication (Auth.js), and talks to the FastAPI backend (`apps/api`) over HTTPS with JWT.

This app does **not** access the database directly. Every read and write goes through the backend.

## Commands

Run from the monorepo root, not from this folder, so npm workspaces resolves correctly:

```bash
npm run dev:web        # Start Next.js dev server on :3000
npm run build:web      # Production build
npm run start:web      # Run the production build
npm run lint:web       # ESLint
```

Or directly from this folder:

```bash
npm run dev
npm run build
npm run lint
```

## Environment variables

Create `apps/web/.env.local` (gitignored). See `.env.example` once it exists.

Expected variables (will grow as sprints progress):

| Variable | Purpose | When added |
|----------|---------|------------|
| `NEXTAUTH_URL` | Base URL for Auth.js callbacks | Sprint 1.1 |
| `JWT_SECRET` | Shared with `apps/api` for JWT verification | Sprint 1.1 |
| `GOOGLE_CLIENT_ID` | Google OAuth | Sprint 1.1 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth | Sprint 1.1 |
| `NEXT_PUBLIC_API_URL` | URL of `apps/api` (e.g. `http://localhost:8000`) | Sprint 1.5 |

## Generated types from the backend

The backend's OpenAPI schema is the contract. TS types are generated into `packages/shared-types` and consumed here as a workspace dependency.

```bash
# From repo root, with apps/api running:
npm run gen:api-types
```

This is set up in Sprint 0.5.4.

## Folder layout

```
apps/web/
├── app/                # App Router routes
│   ├── layout.tsx      # Root layout — fonts, providers
│   └── page.tsx        # Home page
├── components/         # Domain components (added Sprint 1+)
│   └── ui/             # Shadcn/UI primitives (added Sprint 1)
├── lib/                # Client-side utilities
│   ├── auth/           # Auth.js config (Sprint 1)
│   ├── api/            # Thin fetch wrapper using shared-types
│   └── query/          # TanStack Query setup
└── public/             # Static assets
```

## Conventions

- **Server Components by default.** Add `"use client"` at the lowest possible boundary.
- **Tailwind CSS 4 is CSS-native.** No `tailwind.config.js`. Tokens live in `app/globals.css` via `@theme`.
- **No `any`.** Use `unknown` + narrowing at API boundaries.
- See [docs/CONVENTIONS.md](../../docs/CONVENTIONS.md) and [docs/GOTCHAS.md](../../docs/GOTCHAS.md).
