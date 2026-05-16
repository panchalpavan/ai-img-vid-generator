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

import { ArrowUp, ChevronDown, Loader2, Plus } from "lucide-react";
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { ModelConfig } from "@/lib/api/types";

interface PromptBarProps {
  text: string;
  onTextChange: (text: string) => void;
  models: ModelConfig[];
  selectedModelId: string;
  onModelChange: (id: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  className?: string;
}

const MAX_TEXTAREA_HEIGHT_PX = 200;

export function PromptBar({
  text,
  onTextChange,
  models,
  selectedModelId,
  onModelChange,
  onSubmit,
  isPending,
  className,
}: PromptBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  return (
    <form
      onSubmit={handleFormSubmit}
      className={cn(
        "flex flex-col gap-2 rounded-3xl border border-border bg-card p-3 shadow-sm transition-shadow focus-within:shadow-md",
        className,
      )}
    >
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
          {/* Attach button — placeholder, real upload lands in Sprint 4. */}
          <button
            type="button"
            disabled
            title="Attachments coming in Sprint 4"
            className="inline-flex size-9 cursor-not-allowed items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition-colors hover:bg-muted disabled:opacity-60"
            aria-label="Attach (coming soon)"
          >
            <Plus className="size-4" />
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
