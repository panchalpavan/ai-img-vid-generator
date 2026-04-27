# Conventions

## TypeScript
- Strict mode on — no `any`. Use `unknown` + type narrowing at system boundaries.
- Prefer `interface` for object shapes, `type` for unions/intersections.
- Errors: throw typed error classes, not bare `new Error()`. Catch at route/action boundary.
- Async: `async/await` only, no raw `.then()` chains.

## React / Next.js
- Server Components are default. Only add `"use client"` when the component needs event handlers, browser APIs, or React hooks (useState, useEffect, etc.).
- Server Actions for mutations — no separate API routes for simple form handling.
- Collocate components with the route that owns them: `app/generate/GenerateForm.tsx` lives next to `app/generate/page.tsx`.
- Global/shared components go in `components/` at the root (create it when needed).

## File naming
- Files: `kebab-case.tsx` / `kebab-case.ts`
- Components: `PascalCase` (default export name matches filename)
- Utility functions: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE`

## Styling (Tailwind CSS 4)
- Utility-first. Avoid inline styles.
- Design tokens (colors, spacing, fonts) are defined in `app/globals.css` via `@theme {}`.
- No `tailwind.config.js` — configuration is done in CSS.
- Use `cn()` (install `clsx` or `tailwind-merge` when needed) for conditional class merging.

## Imports
- Absolute imports from `@/` (configured in `tsconfig.json`).
- Order: React → Next → third-party → local, separated by blank lines.

## Commits
- Format: `type(scope): description` — e.g. `feat(generate): add image prompt form`
- Types: `feat`, `fix`, `refactor`, `style`, `docs`, `chore`
- Keep commits atomic — one logical change per commit.

## Testing (not yet configured)
- Add `vitest` + `@testing-library/react` before writing the first test.
- Unit tests live next to source: `foo.ts` → `foo.test.ts`.
- E2e tests go in `e2e/` at the root (use Playwright when needed).
