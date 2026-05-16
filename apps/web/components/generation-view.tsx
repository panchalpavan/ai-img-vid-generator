"use client";

/**
 * GenerationView — owns the prompt + result UI and the centered→bottom
 * layout shift.
 *
 * Two visual modes:
 *   - **Empty** (no result yet): the prompt bar sits vertically centered
 *     under a hero headline, ChatGPT-style. First impression.
 *   - **Has result**: the prompt bar pins to the bottom; the result fills
 *     the area above it (scrollable as content grows).
 *
 * State (text, model choice, mutation) lives here so the prompt bar can
 * re-mount across layout modes without losing typed text.
 */

import { useState } from "react";

import { PromptBar } from "@/components/prompt-bar";
import { useGenerate } from "@/lib/api/use-generate";
import { useModels } from "@/lib/api/use-models";
import type { GenerationOutput } from "@/lib/api/types";

export function GenerationView() {
  const { data: models, isLoading: modelsLoading, isError: modelsError } = useModels();
  const generate = useGenerate();

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
  const hasResult = generate.data !== undefined || generate.isError;

  function submit() {
    if (!selectedModel) return;
    generate.mutate({
      model_id: selectedModel.id,
      inputs: {
        text: selectedModel.input_types.includes("text") ? text : null,
        image_urls: [],
      },
    });
  }

  const bar = (
    <PromptBar
      text={text}
      onTextChange={setText}
      models={models}
      selectedModelId={selectedModelId}
      onModelChange={setUserChoice}
      onSubmit={submit}
      isPending={generate.isPending}
      className="w-full max-w-3xl"
    />
  );

  // Has-result layout: result fills the top, bar pinned to bottom.
  if (hasResult) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center">
        <div className="w-full flex-1 overflow-y-auto px-4 py-8">
          <div className="mx-auto w-full max-w-3xl">
            {generate.isError && (
              <ErrorCard
                message={
                  generate.error instanceof Error
                    ? generate.error.message
                    : "Generation failed"
                }
              />
            )}
            {generate.data && <ResultCard output={generate.data} />}
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
          Pick a model, type a prompt, press <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-mono">Enter</kbd>.
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

function ResultCard({ output }: { output: GenerationOutput }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm">
      <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
        Result
      </p>
      {output.output_type === "text" && output.text && (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{output.text}</p>
      )}
      {(output.output_type === "image" || output.output_type === "video") &&
        output.url && (
          <a
            href={output.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm underline"
          >
            Open result
          </a>
        )}
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-5 text-sm text-destructive">
      <p className="mb-1 text-xs uppercase tracking-wide opacity-70">Error</p>
      <p className="whitespace-pre-wrap">{message}</p>
    </div>
  );
}
