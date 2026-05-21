"use client";

/**
 * Unified prompt bar — replaces the old separate Select + Textarea.
 *
 * Layout:
 *   ┌───────────────────────────────────────────────────────────┐
 *   │ <textarea — auto-resizing, single visual line at rest>    │
 *   │ ┌───┐ ┌──────────────┐                              ┌───┐ │
 *   │ │ + │ │ Model name ▾ │                              │ ↑ │ │
 *   │ └───┘ └──────────────┘                              └───┘ │
 *   └───────────────────────────────────────────────────────────┘
 *
 * Controlled component — all state (text, selected model, pending) lives in
 * the parent (GenerationView). Lifting state up means switching layout
 * positions (centered vs bottom-pinned) doesn't drop the user's typed text.
 *
 * Keyboard: Enter submits, Shift+Enter inserts a newline (matches every
 * chat app convention).
 */

import { ArrowUp, ChevronDown, Loader2, Plus, X } from "lucide-react";
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { ModelConfig, ReferenceResponse } from "@/lib/api/types";

interface PromptBarProps {
  text: string;
  onTextChange: (text: string) => void;
  models: ModelConfig[];
  selectedModelId: string;
  onModelChange: (id: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  // Sprint 4A.3 — staged references about to be submitted with the prompt.
  // Owned by the parent so they persist across layout transitions and so
  // the submit handler can pull their URLs.
  references: ReferenceResponse[];
  onPickFiles: (files: File[]) => void;
  onRemoveReference: (id: string) => void;
  isUploading: boolean;
  className?: string;
}

// Accept the same shapes the backend validates against. Keep in sync with
// _ALLOWED_CONTENT_TYPES in apps/api/app/routers/references.py.
const ACCEPTED_FILE_TYPES = "image/png,image/jpeg,image/webp";

const MAX_TEXTAREA_HEIGHT_PX = 200;

export function PromptBar({
  text,
  onTextChange,
  models,
  selectedModelId,
  onModelChange,
  onSubmit,
  isPending,
  references,
  onPickFiles,
  onRemoveReference,
  isUploading,
  className,
}: PromptBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize the textarea up to MAX_TEXTAREA_HEIGHT_PX, then scroll.
  // Runs on every `text` change so paste / typing both reflow correctly.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
  }, [text]);

  const selectedModel = models.find((m) => m.id === selectedModelId);
  const canSubmit = text.trim().length > 0 && !isPending;

  function handleFormSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit();
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits; Shift+Enter inserts newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) onSubmit();
    }
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function handleFilesPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (!list || list.length === 0) return;
    onPickFiles(Array.from(list));
    // Reset so picking the same file twice in a row still fires onChange.
    e.target.value = "";
  }

  return (
    <form
      onSubmit={handleFormSubmit}
      className={cn(
        "flex flex-col gap-2 rounded-3xl border border-border bg-card p-3 shadow-sm transition-shadow focus-within:shadow-md",
        className,
      )}
    >
      {/* Staged reference thumbnails. Empty grid is fine — flex-wrap keeps
          the row visible only when there's something to show. */}
      {references.length > 0 && (
        <div className="flex flex-wrap gap-2 px-1 pt-1">
          {references.map((ref) => (
            <div
              key={ref.id}
              className="group relative size-16 overflow-hidden rounded-lg border border-border bg-muted"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={ref.public_url}
                alt={ref.filename}
                className="size-full object-cover"
              />
              <button
                type="button"
                onClick={() => onRemoveReference(ref.id)}
                aria-label={`Remove ${ref.filename}`}
                className="absolute right-0.5 top-0.5 inline-flex size-5 cursor-pointer items-center justify-center rounded-full bg-background/90 text-foreground shadow-sm opacity-0 transition-opacity hover:bg-background group-hover:opacity-100"
              >
                <X className="size-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe what you want to generate…"
        rows={1}
        className="w-full resize-none border-0 bg-transparent px-2 py-1.5 text-base text-foreground outline-none placeholder:text-muted-foreground/60"
        style={{ maxHeight: MAX_TEXTAREA_HEIGHT_PX }}
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Hidden file input — the visible + button below proxies clicks to
              it. Hiding a real <input type="file"> is the standard pattern;
              styling the native widget across browsers is otherwise painful. */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            multiple
            onChange={handleFilesPicked}
            className="hidden"
            aria-hidden="true"
          />
          <button
            type="button"
            onClick={openFilePicker}
            disabled={isUploading}
            title={isUploading ? "Uploading…" : "Attach reference images"}
            className="inline-flex size-9 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            aria-label="Attach reference images"
          >
            {isUploading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
          </button>

          {/* Model pill */}
          <DropdownMenu>
            <DropdownMenuTrigger
              type="button"
              className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border border-border bg-background px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="max-w-[180px] truncate">
                {selectedModel?.display_name ?? "Select model"}
              </span>
              <ChevronDown className="size-4 opacity-60" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {models.map((m) => (
                <DropdownMenuItem key={m.id} onClick={() => onModelChange(m.id)}>
                  <div className="flex w-full items-center justify-between">
                    <span>{m.display_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {m.cost_in_credits}
                    </span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={!canSubmit}
          aria-label="Generate"
          className="inline-flex size-9 cursor-pointer items-center justify-center rounded-full bg-primary text-primary-foreground transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          {isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowUp className="size-4" />
          )}
        </button>
      </div>
    </form>
  );
}
