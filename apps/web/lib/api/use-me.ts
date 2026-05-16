"use client";

/**
 * useMe() — fetches the current user + balance from FastAPI's /me endpoint.
 *
 * On first call for a new email, FastAPI JIT-provisions the User + Profile
 * rows in Postgres (see apps/api/app/deps/auth.py). So this hook is the
 * frontend trigger that makes a sign-in show up in the database.
 *
 * Cached by TanStack Query under the key `["me"]` — invalidate it via
 * `queryClient.invalidateQueries({ queryKey: ["me"] })` when the user buys
 * credits, completes a generation, etc.
 */

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "./client";
import type { MeResponse } from "./types";

export function useMe() {
  return useQuery<MeResponse>({
    queryKey: ["me"],
    queryFn: () => apiGet<MeResponse>("/me"),
    // Balance can change from underneath us (Stripe webhook, generation
    // debit). 10s staleTime keeps the UI responsive without hammering the
    // API. Caller can invalidate manually after known mutations.
    staleTime: 10_000,
  });
}
