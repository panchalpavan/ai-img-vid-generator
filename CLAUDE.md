# Project: img-vid-generation

@AGENTS.md

## What this is

An image and video generation app built on Next.js 16, React 19, TypeScript, and Tailwind CSS 4. Uses the App Router. Purpose is to learn and experiment with AI-driven media generation workflows.

## Architecture quick map

- Entry: `app/layout.tsx` → `app/page.tsx`
- Style: Tailwind CSS 4 (CSS-native config via `app/globals.css`, no `tailwind.config.js`)
- Toolchain: npm (not pnpm/yarn/bun — always use `npm`)
- Full architecture: `docs/ARCHITECTURE.md` — read before any structural change
- Conventions: `docs/CONVENTIONS.md`
- Sharp edges: `docs/GOTCHAS.md`

## Non-negotiable rules

1. **Always use `npm`** — never pnpm, yarn, or bun.
2. **Before writing any Next.js code**, read the relevant guide in `node_modules/next/dist/docs/`. This version has breaking changes.
3. **TypeScript strict** — no `any`. Use `unknown` + narrowing at boundaries.
4. **Server Components by default** — add `"use client"` only when needed (event handlers, hooks, browser APIs).
5. **No new npm dependencies without noting the reason** in a comment or ADR under `docs/DECISIONS/`.
6. **Run `npm run lint && npm run build`** before calling any change done.

## How to work in this repo

- Use the `wave` skill for any change touching 2+ files or any new feature.
- Delegate codebase exploration to the `explorer` agent before opening more than 3 files yourself.
- No test runner is configured yet — add vitest before writing tests (see `docs/GOTCHAS.md`).
- When uncertain, ask before acting. One question now beats a full revert later.

## Knowledge graph

- Run `/graphify .` to regenerate the codebase knowledge graph after significant changes.
- The graph lives in `graphify-out/` and is consulted automatically via the PreToolUse hook.
