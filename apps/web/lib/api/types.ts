/**
 * Re-exports of types from the generated API schema.
 *
 * Always import API types from this module, never directly from
 * @img-vid-gen/shared-types. That gives us one place to:
 *   - rename, narrow, or extend backend types if needed
 *   - swap to a different codegen tool later
 */

import type { components, paths } from "@img-vid-gen/shared-types";

// ---------------------------------------------------------------------------
// Response models (Pydantic classes on the backend)
// ---------------------------------------------------------------------------
export type HealthResponse = components["schemas"]["HealthResponse"];
export type DBHealthResponse = components["schemas"]["DBHealthResponse"];
export type MeResponse = components["schemas"]["MeResponse"];
// Sprint 2 — adaptive model layer
export type ModelConfig = components["schemas"]["ModelConfig"];
export type InputType = components["schemas"]["InputType"];
export type OutputType = components["schemas"]["OutputType"];
export type ProviderName = components["schemas"]["ProviderName"];
export type GenerationInput = components["schemas"]["GenerationInput"];
export type CreateGenerationRequest = components["schemas"]["CreateGenerationRequest"];
// Sprint 3 — async pipeline
export type GenerationResponse = components["schemas"]["GenerationResponse"];
export type GenerationStatus = components["schemas"]["GenerationStatus"];
// Sprint 4A — reference library
export type ReferenceResponse = components["schemas"]["ReferenceResponse"];
export type PresignRequest = components["schemas"]["PresignRequest"];
export type PresignResponse = components["schemas"]["PresignResponse"];
export type CompleteRequest = components["schemas"]["CompleteRequest"];

// ---------------------------------------------------------------------------
// Per-endpoint shapes — useful when building a typed fetch wrapper later.
// Example: `ResponseFor<"get", "/healthz">` → HealthResponse
// ---------------------------------------------------------------------------
export type ResponseFor<
  M extends keyof paths[P],
  P extends keyof paths,
> = paths[P][M] extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;
