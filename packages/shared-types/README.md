# @img-vid-gen/shared-types

TypeScript types auto-generated from the FastAPI backend's OpenAPI schema. Consumed by `apps/web` as a workspace dependency (`"@img-vid-gen/shared-types": "*"` in its `package.json`).

## Why this exists

The frontend and backend are written in different languages. To keep their contract aligned without writing types by hand on both sides, FastAPI generates an OpenAPI schema for every endpoint, and we run `openapi-typescript` to convert it into TypeScript types.

Every Pydantic request/response model on the FastAPI side becomes a TS type here. No drift, no manual sync — near-tRPC type safety across a polyglot stack.

## How to regenerate

From the monorepo root:

```bash
npm run gen:api-types
```

What that runs, in two steps:

1. `uv --directory apps/api run python -m app.openapi_export > packages/shared-types/openapi.json` — calls `app.openapi()` on the FastAPI app and writes the spec to disk. No HTTP server involved.
2. `openapi-typescript packages/shared-types/openapi.json -o packages/shared-types/api.d.ts` — converts spec to TS.

Both output files are **committed to git** so frontend builds work without needing the backend running.

## How to consume

In `apps/web/`, always import from the local re-export module (which exists so we have one place to add narrowing / adapter logic if we ever need to):

```ts
import type { HealthResponse, DBHealthResponse } from "@/lib/api/types";
```

Direct imports from this package work too, but discouraged outside of `apps/web/lib/api/types.ts`:

```ts
import type { components, paths } from "@img-vid-gen/shared-types";

type HealthResponse = components["schemas"]["HealthResponse"];
```

## What `openapi-typescript` emits

Three top-level exports:

- **`components.schemas`** — every Pydantic model (`HealthResponse`, `DBHealthResponse`, etc.)
- **`paths`** — every URL keyed by HTTP method (`paths["/healthz"]["get"]`)
- **`operations`** — request/response shapes per endpoint, organized by `operationId`

For everyday work, `components.schemas` is what you want. The other two are useful when building a fully-typed fetch wrapper.

## File listing

```
packages/shared-types/
├── package.json          # Workspace member metadata
├── api.d.ts              # Generated TS types (committed)
├── openapi.json          # Generated OpenAPI spec (committed)
└── README.md             # This file
```
