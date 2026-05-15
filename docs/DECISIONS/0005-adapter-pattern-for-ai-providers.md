# ADR 0005: Adapter pattern for AI providers

**Status:** Accepted
**Date:** 2026-04-28

## Context

The app currently uses Google AI Studio (Gemini). It will later add Sjinn for premium video models and migrate to Vertex AI for GCP-native Gemini. Each provider has different:
- SDKs and authentication
- Input shapes (text-only vs multimodal vs image-to-video)
- Latency profile (Gemini is sync-ish, Sjinn is async with polling)
- Cost per generation

Without a unifying abstraction, every provider addition becomes a UI rewrite and a pipeline rewrite.

## Decision

Implement a **model registry** at `lib/models.ts` with a `ModelConfig` discriminated union type:

```ts
type ModelConfig = {
  id: string;                          // 'gemini-2.0-flash', 'sjinn-veo3', etc.
  provider: 'google-ai-studio' | 'vertex-ai' | 'sjinn';
  displayName: string;
  inputTypes: ('text' | 'image' | 'video')[];
  isAsync: boolean;
  costInCredits: number;
};
```

Each provider has a corresponding adapter module (`lib/providers/google-ai-studio.ts`, `lib/providers/sjinn.ts`, etc.) implementing a common interface:

```ts
interface ProviderAdapter {
  generate(input: GenerationInput): Promise<GenerationResult | JobHandle>;
  pollStatus?(jobId: string): Promise<JobStatus>;  // only async providers
}
```

The form, credit deduction, and pipeline logic depend only on `ModelConfig` — never on a specific provider.

## Consequences

**Positive:**
- Adding Sjinn in Sprint 6 is a config addition + one adapter file. No UI changes. No pipeline changes.
- Migrating Gemini from AI Studio → Vertex AI in Sprint 7 is swapping one adapter file. The model ID stays `gemini-2.0-flash`.
- Dynamic forms can be generated from `inputTypes` — no per-provider form code.
- Cost differentiation is data-driven via `costInCredits` — no `if (provider === 'sjinn')` branching.

**Negative:**
- Initial abstraction cost in Sprint 2 — slightly more code than a direct Gemini call would be.
- Common interface must accommodate the most demanding provider (async polling), making it slightly heavier than a sync-only interface.

## Alternatives considered

- **Direct provider calls per route:** Rejected — every new provider becomes a copy-paste of the entire pipeline, and provider migration is a rewrite.
- **Vercel AI SDK:** Considered. Covers some providers but not Sjinn, and abstracts in directions we don't need (streaming chat). May still be used as the Gemini adapter implementation, but the registry abstraction sits above it.
