"use client";

/**
 * GenerationView — owns the prompt + result UI for the async pipeline.
 *
 * Sprint 3 contract: POST /generations returns a `pending` row, and the
 * Celery worker drives it to `processing` → `done | failed`. We use
 * `useGenerate` to submit and `useGeneration(id)` to poll.
 *
 * Visual states:
 *   - **idle**     — no generation submitted yet → hero + centered bar.
 *   - **inflight** — pending or processing → bar pinned to bottom, spinner above.
 *   - **done**     — result rendered, bar pinned to bottom, free to submit next.
 *   - **failed**   — error rendered, bar pinned to bottom.
 *
 * The submit button is disabled while a generation is inflight to keep the
 * UI single-track for Sprint 3. (Multi-track queueing is a future polish.)
 */

import { useState } from "react";

import { PromptBar } from "@/components/prompt-bar";
import { useGenerate } from "@/lib/api/use-generate";
import { useGeneration } from "@/lib/api/use-generation";
import { useModels } from "@/lib/api/use-models";
import {
  useDeleteReference,
  useUploadReference,
} from "@/lib/api/use-references";
import type { GenerationResponse, ReferenceResponse } from "@/lib/api/types";

const TERMINAL_STATUSES = new Set<GenerationResponse["status"]>([
  "done",
  "failed",
]);

export function GenerationView() {
  const { data: models, isLoading: modelsLoading, isError: modelsError } = useModels();
  const generate = useGenerate();

  // `generate.data` survives across renders until the next mutation starts,
  // giving us a natural "current generation id" without extra state.
  const activeId = generate.data?.id;
  const generation = useGeneration(activeId);

  const [text, setText] = useState("");
  const [userChoice, setUserChoice] = useState<string | undefined>(undefined);

  // Staged references — uploaded refs queued for the next submit. Not the
  // same as the full library (that's `useReferences()` in the gallery). When
  // a generation submits we'll pass these refs' public_urls as image_urls
  // (Sprint 4A.4). Removing a staged ref also deletes it from R2 + DB so the
  // user's library doesn't accumulate one-off uploads.
  const [stagedRefs, setStagedRefs] = useState<ReferenceResponse[]>([]);
  const uploadReference = useUploadReference();
  const deleteReference = useDeleteReference();

  async function handlePickFiles(files: File[]) {
    // Upload sequentially rather than in parallel — easier to reason about
    // errors (one failure doesn't leave half the batch in limbo), and the
    // user typically attaches one or two files at a time. Re-evaluate if
    // batch uploads become common.
    for (const file of files) {
      try {
        const ref = await uploadReference.mutateAsync(file);
        setStagedRefs((prev) => [...prev, ref]);
      } catch (err) {
        // Surface the failure inline next time we add a toast layer; for
        // now the error is logged so the user isn't left wondering.
        console.error("Reference upload failed", err);
      }
    }
  }

  function handleRemoveStagedRef(id: string) {
    setStagedRefs((prev) => prev.filter((r) => r.id !== id));
    // Fire-and-forget delete — we don't block the UI on it. If it fails the
    // ref stays in the library, harmless (next list call will show it).
    deleteReference.mutate(id);
  }

  if (modelsLoading) {
    return <CenteredMessage>Loading models…</CenteredMessage>;
  }
  if (modelsError || !models || models.length === 0) {
    return <CenteredMessage tone="error">No models available.</CenteredMessage>;
  }

  const selectedModelId = userChoice ?? models[0].id;
  const selectedModel = models.find((m) => m.id === selectedModelId);

  const isInflight = Boolean(
    generation.data && !TERMINAL_STATUSES.has(generation.data.status),
  );
  const showResultArea = Boolean(generate.data || generate.isError);

  function submit() {
    if (!selectedModel) return;
    generate.mutate(
      {
        model_id: selectedModel.id,
        inputs: {
          text: selectedModel.input_types.includes("text") ? text : null,
          // Sprint 4A.4 — pass staged refs' public URLs as multimodal input.
          // The Seegen adapter will pick these up as its `urls` array and
          // switch to image-to-image mode automatically. Other adapters
          // (Pollinations, Gemini text) ignore image_urls — no special-casing.
          image_urls: stagedRefs.map((r) => r.public_url),
        },
      },
      {
        // Clear the textarea once the submit is accepted by the backend,
        // matching every chat UI convention. The user can immediately start
        // typing the next prompt while the worker runs.
        onSuccess: () => {
          setText("");
          // Clear staged refs from the bar — they're "used" now. The DB
          // rows stay (they're in the user's library and we may add a
          // gallery picker later); they just aren't pre-staged anymore.
          setStagedRefs([]);
        },
      },
    );
  }

  const bar = (
    <PromptBar
      text={text}
      onTextChange={setText}
      models={models}
      selectedModelId={selectedModelId}
      onModelChange={setUserChoice}
      onSubmit={submit}
      // Disabled while: the POST is in flight, OR the worker is still
      // crunching the previous generation.
      isPending={generate.isPending || isInflight}
      references={stagedRefs}
      onPickFiles={handlePickFiles}
      onRemoveReference={handleRemoveStagedRef}
      isUploading={uploadReference.isPending}
      className="w-full max-w-3xl"
    />
  );

  // Reset the mutation state (and incidentally stop polling, since
  // useGeneration's `enabled` depends on generate.data?.id). The textarea
  // is intentionally NOT cleared — the user may want to tweak and retry.
  // The DB row for the previous generation stays; we'll show it in a
  // "history" gallery later.
  function clearResult() {
    generate.reset();
  }

  // Has-anything-yet layout: result/inflight area on top, bar pinned bottom.
  if (showResultArea) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center">
        <div className="w-full flex-1 overflow-y-auto px-4 py-8">
          <div className="mx-auto w-full max-w-3xl space-y-4">
            <div className="flex justify-start">
              <button
                type="button"
                onClick={clearResult}
                disabled={isInflight}
                className="cursor-pointer rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
              >
                ← New generation
              </button>
            </div>
            <GenerationStateView
              postError={generate.error}
              generation={generation.data}
              pollError={generation.error}
            />
          </div>
        </div>
        <div className="w-full px-4 pb-6">
          <div className="mx-auto flex w-full max-w-3xl justify-center">
            {bar}
          </div>
        </div>
      </div>
    );
  }

  // Empty layout: hero + bar, vertically centered.
  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-8 px-4">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Where should we begin?
        </h1>
        <p className="text-muted-foreground">
          Pick a model, type a prompt, press{" "}
          <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-mono">
            Enter
          </kbd>
          .
        </p>
      </div>
      {bar}
    </div>
  );
}

function CenteredMessage({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "error";
}) {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center px-4 text-center">
      <p
        className={
          tone === "error" ? "text-sm text-destructive" : "text-sm text-muted-foreground"
        }
      >
        {children}
      </p>
    </div>
  );
}

/**
 * Renders the right thing for whatever state the generation is in.
 * Order of precedence: POST error → row failed → row done → in flight.
 */
function GenerationStateView({
  postError,
  generation,
  pollError,
}: {
  postError: Error | null;
  generation: GenerationResponse | undefined;
  pollError: Error | null;
}) {
  if (postError) {
    return (
      <ErrorCard
        title="Submit failed"
        message={postError instanceof Error ? postError.message : String(postError)}
      />
    );
  }
  if (!generation) {
    // POST returned but polling hasn't gotten data yet — should be brief.
    return <PendingCard label="Submitting…" />;
  }
  if (generation.status === "failed") {
    return (
      <ErrorCard
        title="Generation failed"
        message={generation.error ?? "Unknown error"}
      />
    );
  }
  if (generation.status === "done") {
    return <ResultCard generation={generation} />;
  }
  if (pollError) {
    return (
      <ErrorCard
        title="Couldn't fetch status"
        message={pollError instanceof Error ? pollError.message : String(pollError)}
      />
    );
  }
  return (
    <PendingCard
      label={generation.status === "processing" ? "Generating…" : "Queued…"}
      prompt={generation.prompt}
    />
  );
}

function ResultCard({ generation }: { generation: GenerationResponse }) {
  // result_url can be either a data: URI (Sprint 3.5 stopgap) or an https
  // URL (once R2 storage lands). Treat anything starting with `data:image/`
  // or ending in a known image extension as an image to inline.
  const isImageUrl =
    !!generation.result_url &&
    (generation.result_url.startsWith("data:image/") ||
      /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(generation.result_url));

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
        <p className="mb-1 text-xs uppercase tracking-wide opacity-70">Prompt</p>
        <p className="whitespace-pre-wrap">{generation.prompt}</p>
      </div>
      <div className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm">
        <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
          Result
        </p>
        {generation.result_text && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {generation.result_text}
          </p>
        )}
        {isImageUrl && (
          // Plain <img> intentionally — Next.js <Image> doesn't optimize
          // data: URIs, and we don't know the dimensions ahead of time.
          // When R2 lands and result_url becomes a real CDN URL, we can
          // revisit using <Image> for resizing.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={generation.result_url ?? ""}
            alt={generation.prompt}
            className="max-h-[70vh] w-full rounded-lg object-contain"
          />
        )}
        {generation.result_url && !isImageUrl && (
          <a
            href={generation.result_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm underline"
          >
            Open result
          </a>
        )}
      </div>
    </div>
  );
}

function PendingCard({ label, prompt }: { label: string; prompt?: string }) {
  return (
    <div className="space-y-4">
      {prompt && (
        <div className="rounded-2xl border border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
          <p className="mb-1 text-xs uppercase tracking-wide opacity-70">Prompt</p>
          <p className="whitespace-pre-wrap">{prompt}</p>
        </div>
      )}
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-card p-5 text-sm text-card-foreground shadow-sm">
        <span className="inline-block size-2 animate-pulse rounded-full bg-primary" />
        {label}
      </div>
    </div>
  );
}

/**
 * Maps a raw upstream error string to a friendly heading + suggestion.
 * The raw message goes under a collapsed "Show details" toggle so users
 * see actionable copy first, not a wall of protobuf-looking text.
 */
function parseError(message: string): {
  headline: string;
  suggestion: string | null;
} {
  if (/quota|rate.?limit|\b429\b|exceeded.*limit/i.test(message)) {
    return {
      headline: "Rate limit hit.",
      suggestion:
        "This model's free quota is exhausted. Try a different model from the dropdown — Pollinations FLUX has no quota.",
    };
  }
  if (/\b50[023]\b|unavailable|temporarily/i.test(message)) {
    return {
      headline: "Provider is unavailable.",
      suggestion: "The AI provider is having issues. Try again in a minute.",
    };
  }
  if (/insufficient credits/i.test(message)) {
    return {
      headline: "Not enough credits.",
      suggestion: "Buy more credits (Sprint 5) or use a model with a lower cost.",
    };
  }
  if (/\b403\b|forbidden/i.test(message)) {
    return {
      headline: "Request blocked by the provider.",
      suggestion:
        "The provider rejected the request — possibly bot detection or a missing key. Try a different model from the dropdown.",
    };
  }
  if (/unauthor|\b401\b/i.test(message)) {
    return {
      headline: "Authentication problem.",
      suggestion: "Sign out and back in. If that doesn't help, the provider key may be invalid.",
    };
  }
  // Fallback: first line of the message, truncated.
  return {
    headline: message.split("\n")[0].slice(0, 160),
    suggestion: null,
  };
}

function ErrorCard({ title, message }: { title: string; message: string }) {
  const [showDetails, setShowDetails] = useState(false);
  const friendly = parseError(message);

  return (
    <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-5 text-sm">
      <p className="mb-2 text-xs uppercase tracking-wide text-destructive/80">
        {title}
      </p>
      <p className="font-medium text-destructive">{friendly.headline}</p>
      {friendly.suggestion && (
        <p className="mt-2 text-foreground/80">{friendly.suggestion}</p>
      )}
      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        className="mt-3 cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:underline"
      >
        {showDetails ? "Hide details" : "Show technical details"}
      </button>
      {showDetails && (
        <pre className="mt-2 max-h-60 overflow-auto rounded-md border border-border/50 bg-background/50 p-3 text-xs whitespace-pre-wrap text-muted-foreground">
          {message}
        </pre>
      )}
    </div>
  );
}
