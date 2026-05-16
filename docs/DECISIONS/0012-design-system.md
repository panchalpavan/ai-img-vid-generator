# ADR 0012: Design system — Shadcn/UI, system-preference dark mode, top-nav shell

**Status:** Accepted
**Date:** 2026-05-16

## Context

Sprint 1.6 forced an explicit choice on a set of UI decisions that had been deferred. Earlier discussion (during Sprint 1.1 prep) recommended Option B: make these decisions when installing Shadcn/UI in Sprint 1.6 rather than design-in-a-vacuum upfront or paper-over-it-with-defaults indefinitely.

Decisions touch: component library, color palette, theme strategy (dark/light), layout shape, icon library, typography, border radius. Each has reasonable defaults and each can be swapped later if a stronger preference emerges.

## Decision

### Component library — Shadcn/UI

Generated TypeScript components (not an npm package). Each component is a copy-paste of source we own under `apps/web/components/ui/`, built on Radix UI primitives + Tailwind utility classes.

Why: no opinionated theme baked into a library, full control over styling, no library version lock-in. Industry standard for serious Next.js apps in 2025-2026.

Setup: `npx shadcn@latest init` (project config in `components.json`), components added on demand via `npx shadcn@latest add <name>`.

### Color palette — neutral / zinc

Shadcn's neutral base color. Grayscale primary, no opinionated accent hue baked in. Easy to overlay a brand color later by adjusting one CSS variable.

Color space: **OKLCH** (Shadcn 2026 default). Perceptually uniform; lightness adjustments behave intuitively. Modern browsers all support it.

### Theme strategy — system-preference with class-based toggle

- Library: `next-themes`
- Mode: `defaultTheme="system"` + `enableSystem` — follows the user's OS preference automatically.
- Switching mechanism: adds a `.dark` class to `<html>`. Matches Shadcn's `@custom-variant dark (&:is(.dark *))` convention.
- No user-facing toggle yet. The infrastructure is ready when one is wanted.

Why not media-query-only: media queries can't be overridden, so adding a toggle later would require reworking the whole approach. next-themes leaves the door open for free.

### Layout shape — sticky top navbar only

Single persistent shell in `apps/web/app/layout.tsx`:
- Top sticky navbar with the app name, credit badge, user menu (when authenticated)
- Main content fills the rest

No sidebar yet. A sidebar adds visual weight and screen-real-estate cost that isn't justified at the current feature count (~1 main view). Easy to introduce later by changing the layout JSX — no architectural change required.

### Icons — lucide-react

Shadcn's default icon library. Tree-shakable, consistent style, ~1300 icons. Pulled in transitively by Shadcn components.

### Typography

Existing: **Geist Sans + Geist Mono** (Vercel's fonts, loaded via `next/font/google`). Geist is the default for `create-next-app` and pairs well with the neutral palette.

No serif. No custom font loading.

### Border radius

`--radius: 0.625rem` (Shadcn default). Slightly softer than Tailwind's default `rounded-md`. Derived radii (`sm`, `md`, `lg`, `xl`, `2xl`, …) are calculated as multiples in `app/globals.css`.

## Consequences

**Positive:**
- Every UI primitive added in future sprints will look consistent — Shadcn's design tokens propagate everywhere via Tailwind classes.
- Dark mode just works on every component because Shadcn components reference token variables (e.g., `bg-background`) that flip with the theme.
- Swapping the accent color to a brand color later is a one-line CSS variable change.
- Generated TS code means breaking changes never come from a library update — we'd see them in our own diffs first.

**Negative:**
- Shadcn components live under our `components/ui/`. We own their maintenance. Updates require running `npx shadcn add <name>` again (which can overwrite local customizations).
- `next-themes` adds a small dep and forces `suppressHydrationWarning` on `<html>` to avoid the OS-theme-detection hydration mismatch. Documented in the layout.
- Component cookie-cutting (vs. authoring from scratch) means we might end up with unused props/variants. Acceptable cost.

## Alternatives considered

- **Material UI / Chakra / Mantine.** Rejected. Heavy themed component libraries lock you into their design language. Hard to break out of "this is a MUI app" look. Shadcn's "copy-paste" model avoids this entirely.
- **Plain Tailwind (no component library).** Considered. Would force us to build common primitives (Dropdown, Avatar, Dialog) from scratch — large up-front cost without much learning value at this stage. We can always extract Shadcn components into our own primitives later.
- **Media-query-only dark mode (no `next-themes`).** Considered. Simpler but precludes a future toggle. Decided the toggle option is worth the small dep.
- **Sidebar layout.** Premature. One main view doesn't need sidebar navigation. Revisit when feature count justifies it.
- **Tailwind v3 + tailwind.config.js.** Rejected. Tailwind 4 (CSS-native config) is already in place; downgrading would lose Vite-style HMR + smaller bundles.

## Pointers

- Component library config: `apps/web/components.json`
- Design tokens (colors, radius, dark mode): `apps/web/app/globals.css`
- Theme provider: `apps/web/lib/theme/provider.tsx`
- Navbar shell: `apps/web/components/navbar.tsx`
