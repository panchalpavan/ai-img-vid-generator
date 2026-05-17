"use client";

/**
 * useGeneration(id) — polls GET /generations/{id} until status is terminal.
 *
 * Polls every 1s while `pending` or `processing`. Stops the moment status
 * is `done` or `failed`. When status transitions to a terminal state on a
 * non-dev user, also invalidates ["me"] so the credit badge reflects the
 * post-deduction balance.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { apiGet } from "./client";
import type { GenerationResponse } from "./types";

const POLL_INTERVAL_MS = 1000;
const TERMINAL_STATUSES = new Set<GenerationResponse["status"]>([
  "done",
  "failed",
]);

export function useGeneration(id: string | undefined) {
  const queryClient = useQueryClient();

  const query = useQuery<GenerationResponse>({
    queryKey: ["generation", id],
    queryFn: () => apiGet<GenerationResponse>(`/generations/${id}`),
    enabled: !!id,
    // Poll until the status is terminal. Returning `false` from
    // refetchInterval pauses polling without unmounting the query.
    refetchInterval: (q) => {
      const data = q.state.data;
      if (data && TERMINAL_STATUSES.has(data.status)) return false;
      return POLL_INTERVAL_MS;
    },
    refetchIntervalInBackground: false, // don't burn bandwidth on hidden tabs
  });

  // Invalidate the balance once a generation lands. Doing this in an effect
  // (not inside the queryFn) means it fires exactly once per terminal
  // transition, regardless of how many times useGeneration re-renders.
  const status = query.data?.status;
  useEffect(() => {
    if (status && TERMINAL_STATUSES.has(status)) {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  }, [status, queryClient]);

  return query;
}
