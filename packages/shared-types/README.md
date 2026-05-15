# packages/shared-types

> **Status:** Empty until Sprint 0.5.4 wires up OpenAPI codegen.

TypeScript types auto-generated from the FastAPI backend's OpenAPI schema. Consumed by `apps/web` as a workspace dependency.

## Why this exists

The frontend and backend are written in different languages. To keep their contract aligned without hand-writing types twice, FastAPI generates an OpenAPI schema for every endpoint, and we use `openapi-typescript` to convert it into TS types.

Result: every Pydantic request/response model on the FastAPI side becomes a TypeScript type here. No drift, no manual sync, near-tRPC type safety across the language boundary.

## How to regenerate

From the monorepo root (with `apps/api` dev server running):

```bash
npm run gen:api-types
```

That command (set up in Sprint 0.5.4) runs:
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o packages/shared-types/api.d.ts
```

The generated file is **committed to git** so frontend builds work without needing the backend running.

## How to consume

In `apps/web/`:

```ts
import type { paths, components } from "@img-vid-gen/shared-types";

type CreateGenerationRequest = components["schemas"]["CreateGenerationRequest"];
```

(Workspace package name is set in Sprint 0.5.4 when this package gets its `package.json`.)
