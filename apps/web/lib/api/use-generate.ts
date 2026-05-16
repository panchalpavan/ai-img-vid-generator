"use client";

/**
 * useGenerate() — mutation hook for POST /generations.
 *
 * Returns a TanStack Query `useMutation` result, so callers get:
 *   - `mutate(req)` / `mutateAsync(req)` to fire the call
 *   - `isPending`, `isError`, `error`, `data` for UI state
 *
 * On success we invalidate ["me"] so the credit badge re-fetches the
 * new balance. (Sprint 2 doesn't actually deduct credits yet — that's
 * Sprint 3 — but wiring the invalidation now means no follow-up edit.)
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPost } from "./client";
import type { CreateGenerationRequest, GenerationOutput } from "./types";

export function useGenerate() {
  const queryClient = useQueryClient();
  return useMutation<GenerationOutput, Error, CreateGenerationRequest>({
    mutationFn: (req) =>
      apiPost<CreateGenerationRequest, GenerationOutput>("/generations", req),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
