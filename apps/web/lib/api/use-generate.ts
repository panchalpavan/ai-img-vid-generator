"use client";

/**
 * useGenerate() — mutation hook for POST /generations.
 *
 * Sprint 3 changed the contract: the endpoint is now async. POST returns
 * a `GenerationResponse` row in status `pending`, and the actual work
 * happens on a Celery worker. The caller is expected to take the returned
 * `id` and poll `GET /generations/{id}` (via `useGeneration`) until
 * status is terminal.
 *
 * `onSuccess` invalidates the ["me"] query because credits will get
 * deducted asynchronously on the worker — the cached balance is stale
 * the moment the task picks up the row.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPost } from "./client";
import type { CreateGenerationRequest, GenerationResponse } from "./types";

export function useGenerate() {
  const queryClient = useQueryClient();
  return useMutation<GenerationResponse, Error, CreateGenerationRequest>({
    mutationFn: (req) =>
      apiPost<CreateGenerationRequest, GenerationResponse>("/generations", req),
    onSuccess: (data) => {
      // Prime the cache for the new row so the polling query starts with
      // data instead of an "isLoading" flash.
      queryClient.setQueryData(["generation", data.id], data);
      // Balance will change on the worker; refresh.
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
