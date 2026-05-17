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
import type { GenerationResponse } from "@/lib/api/types";

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
          image_urls: [],
        },
      },
      {
        // Clear the textarea once the submit is accepted by the backend,
        // matching every chat UI convention. The user can immediately start
        // typing the next prompt while the worker runs.
        onSuccess: () => setText(""),
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
      className="w-full max-w-3xl"
    />
  );

  // Has-anything-yet layout: result/inflight area on top, bar pinned bottom.
  if (showResultArea) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center">
        <div className="w-full flex-1 overflow-y-auto px-4 py-8">
          <div className="mx-auto w-full max-w-3xl">
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
        {generation.result_url && (
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

function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-5 text-sm text-destructive">
      <p className="mb-1 text-xs uppercase tracking-wide opacity-70">{title}</p>
      <p className="whitespace-pre-wrap">{message}</p>
    </div>
  );
}
