# Gotchas & Sharp Edges

## Next.js 16 — read the docs, don't assume
This version has breaking changes from what most training data knows. **Before writing any Next.js code**, read the relevant guide in:
```
node_modules/next/dist/docs/
```
Heed deprecation notices — APIs you know may have changed signatures or been removed.

## Tailwind CSS 4 — no config file
Tailwind 4 uses a CSS-native configuration model. There is **no `tailwind.config.js`**. All theme customization happens in `app/globals.css` using `@theme {}` blocks and CSS custom properties. Do not create a `tailwind.config.js` unless the docs say otherwise.

## React 19 — new APIs
React 19 ships `use()`, `useActionState`, `useFormStatus`, `useOptimistic`, and changes to `ref` handling (no more `forwardRef` needed). These are available and preferred over the older patterns.

## Server vs Client Components — the boundary
Passing a non-serializable value (function, class instance, Date) from a Server Component to a Client Component will throw at runtime. Keep the boundary clean: only pass plain objects, strings, numbers, and arrays across it. Use Server Actions for callbacks.

## `npm run lint` — no `--max-warnings`
The current `eslint` script in `package.json` is bare. Any ESLint warnings pass silently. When tightening, add `--max-warnings=0` to the script.

## No test runner configured
There are zero tests in this repo. Before writing the first test, install vitest:
```bash
npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/user-event jsdom
```
Then add a `vitest.config.ts` and a `"test"` script to `package.json`.

## `npm run build` as the final gate
Until a test suite exists, `npm run build` (which includes TypeScript type-checking via Next.js) is the primary correctness gate. Always run it before calling a change done.
