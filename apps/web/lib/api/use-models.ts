"use client";

/**
 * useModels() — fetches the list of available AI models from FastAPI.
 *
 * The list is static for the lifetime of a backend process (the registry
 * is built at boot), so we give it a long staleTime to avoid pointless
 * refetches.
 */

import { useQuery } from "@tanstack/react-query";

import { apiGetPublic } from "./client";
import type { ModelConfig } from "./types";

export function useModels() {
  return useQuery<ModelConfig[]>({
    queryKey: ["models"],
    queryFn: () => apiGetPublic<ModelConfig[]>("/models"),
    // Models don't change at runtime; cache long.
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}
