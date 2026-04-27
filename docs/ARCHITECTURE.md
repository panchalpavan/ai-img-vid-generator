# Architecture

## Stack
| Layer | Technology | Version |
|---|---|---|
| Framework | Next.js (App Router) | 16.2.4 |
| UI | React | 19.2.4 |
| Language | TypeScript (strict) | ^5 |
| Styling | Tailwind CSS | ^4 |
| Linting | ESLint 9 + eslint-config-next | ^9 |
| Package manager | npm | (use npm always) |

## File structure
```
app/
  layout.tsx       # Root layout — fonts, global providers, html shell
  page.tsx         # Home page (Server Component)
  globals.css      # Tailwind CSS 4 base + design tokens
public/            # Static assets served at /
docs/              # Architecture, conventions, decisions, gotchas, plans
.claude/           # Claude Code agents, skills, hooks, settings
```

## Key architectural decisions
- **App Router only** — no Pages Router. All routing lives under `app/`.
- **Server Components by default** — React Server Components are the default. Add `"use client"` at the lowest possible boundary.
- **Tailwind CSS 4 config is CSS-native** — there is no `tailwind.config.js`. Design tokens and customizations go in `app/globals.css` using `@theme` and CSS variables.
- **No state management library yet** — use React built-ins (useState, useContext, Server Actions) until a clear need emerges.

## Data flow (planned)
```
User → Next.js Route (Server Component)
  → API Route / Server Action
  → External AI provider (image/video generation API)
  → Streamed response back to client
```

## Adding new routes
Create a folder under `app/` with a `page.tsx`. Layouts cascade automatically. Loading and error states go in `loading.tsx` and `error.tsx` siblings.
