"use client";

/**
 * Generations gallery — the "/history" route's main UI.
 *
 * Grid of past generations, newest first. Each card shows a thumbnail
 * (image generation) or a text snippet (text generation), plus the model
 * name and a relative timestamp. Clicking a card opens a detail modal
 * with the full prompt + result.
 *
 * Pagination is page-based (12 per page) with a Load More button rather
 * than infinite scroll — explicit user action, predictable URL state
 * once we plumb the offset into a query param later, and trivially
 * accessible with a keyboard.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useGenerationsList, PAGE_SIZE } from "@/lib/api/use-generations";
import { cn } from "@/lib/utils";
import type { GenerationResponse } from "@/lib/api/types";

export function GenerationsGallery() {
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useGenerationsList(offset);

  // When the user invalidates the cache somewhere (e.g. a new generation
  // finishes on the home page), reset back to page 0 so they see the
  // freshest result. This effect only fires on offset-not-zero plus
  // success, so the typical "user is paging" case isn't disturbed.
  // (Future polish: invalidate on focus.)
  const queryClient = useQueryClient();
  useEffect(() => {
    return () => {
      // On unmount, drop the cached pages so we don't show a stale view
      // when the user navigates back. Cheap — TanStack will refetch.
      void queryClient.invalidateQueries({ queryKey: ["generations", "list"] });
    };
  }, [queryClient]);

  if (query.isLoading) {
    return <CenteredMessage>Loading your generations…</CenteredMessage>;
  }
  if (query.isError) {
    return (
      <CenteredMessage tone="error">
        Couldn't load generations: {query.error.message}
      </CenteredMessage>
    );
  }

  const rows = query.data ?? [];
  if (rows.length === 0 && offset === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <h2 className="text-xl font-semibold tracking-tight">No generations yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Head back to the generate page, type a prompt, and your results will
          show up here.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex h-9 cursor-pointer items-center rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Start generating
        </Link>
      </div>
    );
  }

  const openRow = openId ? rows.find((r) => r.id === openId) : null;
  // Heuristic: if we got back a full page, there might be more. If we
  // got less, this is definitely the last page. The DB has no count
  // endpoint today; this is good enough for a learning project and
  // sidesteps a count(*) query on every page load.
  const hasMore = rows.length === PAGE_SIZE;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">My generations</h1>
        <Link
          href="/"
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
        >
          ← Back to generate
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {rows.map((row) => (
          <GenerationCard
            key={row.id}
            row={row}
            onOpen={() => setOpenId(row.id)}
          />
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Showing {offset + 1}–{offset + rows.length}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0 || query.isFetching}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="inline-flex h-8 cursor-pointer items-center rounded-full border border-border px-3 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            ← Newer
          </button>
          <button
            type="button"
            disabled={!hasMore || query.isFetching}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="inline-flex h-8 cursor-pointer items-center rounded-full border border-border px-3 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            {query.isFetching ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              "Older →"
            )}
          </button>
        </div>
      </div>

      {openRow && (
        <DetailModal row={openRow} onClose={() => setOpenId(null)} />
      )}
    </div>
  );
}

function GenerationCard({
  row,
  onOpen,
}: {
  row: GenerationResponse;
  onOpen: () => void;
}) {
  const isImage =
    !!row.result_url &&
    /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(row.result_url);

  return (
    <button
      type="button"
      onClick={onOpen}
      // `relative` is the positioning context for the absolute-positioned
      // prompt overlay below; without it the overlay anchors to the
      // viewport and the hover text appears in the corner of the page.
      className="group relative flex aspect-square cursor-pointer flex-col overflow-hidden rounded-xl border border-border bg-muted/30 text-left transition-colors hover:border-primary"
    >
      {row.status === "done" && isImage && row.result_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={row.result_url}
          alt={row.prompt}
          className="size-full object-cover transition-transform group-hover:scale-105"
          loading="lazy"
        />
      ) : row.status === "done" && row.result_text ? (
        <div className="flex size-full flex-col gap-1 p-3 text-xs">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            text
          </span>
          <span className="line-clamp-6 text-foreground/80">
            {row.result_text}
          </span>
        </div>
      ) : row.status === "done" ? (
        // Legacy rows from Sprint 3.5: data URI was NULL'd by Alembic
        // `2724c5210cfe` when we shrank result_url. Row metadata (prompt,
        // model, timestamp) is preserved but the image bytes are gone.
        <div className="flex size-full flex-col items-center justify-center gap-1 p-3 text-center text-xs text-muted-foreground/70">
          <span className="text-2xl opacity-50">⛌</span>
          <span>Result no longer available</span>
        </div>
      ) : (
        <div className="flex size-full items-center justify-center p-3 text-center text-xs">
          <StatusBadge status={row.status} />
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 bg-gradient-to-t from-black/70 via-black/30 to-transparent p-2 opacity-0 transition-opacity group-hover:opacity-100">
        <span className="line-clamp-2 text-[10px] text-white/90">
          {row.prompt}
        </span>
      </div>
    </button>
  );
}

function StatusBadge({ status }: { status: GenerationResponse["status"] }) {
  const label = status;
  const tone =
    status === "failed"
      ? "text-destructive"
      : status === "done"
        ? "text-foreground/60"
        : "text-foreground/80";
  return (
    <span className={cn("text-xs uppercase tracking-wide", tone)}>
      {label}
    </span>
  );
}

function DetailModal({
  row,
  onClose,
}: {
  row: GenerationResponse;
  onClose: () => void;
}) {
  useEffect(() => {
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  const isImage =
    !!row.result_url &&
    /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(row.result_url);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-3xl rounded-2xl border border-border bg-card p-6 shadow-xl"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 inline-flex size-8 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" />
        </button>

        <div className="mb-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{row.model_id}</span>
          <span aria-hidden>·</span>
          <span>{new Date(row.created_at).toLocaleString()}</span>
          <span aria-hidden>·</span>
          <StatusBadge status={row.status} />
        </div>

        <div className="mb-4 rounded-xl border border-border/60 bg-muted/30 p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Prompt
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm">{row.prompt}</p>
        </div>

        {row.status === "done" && isImage && row.result_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={row.result_url}
            alt={row.prompt}
            className="max-h-[70vh] w-full rounded-lg object-contain"
          />
        )}
        {row.status === "done" && row.result_text && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {row.result_text}
          </p>
        )}
        {row.status === "failed" && row.error && (
          <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
            {row.error}
          </pre>
        )}
      </div>
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
        className={cn(
          "text-sm",
          tone === "error" ? "text-destructive" : "text-muted-foreground",
        )}
      >
        {children}
      </p>
    </div>
  );
}
