"use client";

/**
 * useGenerationsList — paginated list of the user's past generations.
 *
 * Returns one TanStack page at a time (limit/offset). The gallery UI
 * tracks `offset` in local state and bumps it on "Load more"; we don't
 * use `useInfiniteQuery` because TanStack's pagination cache model lets
 * us evict / refresh individual pages more cleanly when the user deletes
 * one (Sprint 6.7+ — delete from gallery).
 */

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "./client";
import type { GenerationResponse } from "./types";

const PAGE_SIZE = 12;

export function useGenerationsList(offset: number = 0, limit: number = PAGE_SIZE) {
  return useQuery<GenerationResponse[], Error>({
    queryKey: ["generations", "list", { offset, limit }],
    queryFn: () =>
      apiGet<GenerationResponse[]>(
        `/generations?limit=${limit}&offset=${offset}`,
      ),
    // Keep previous page visible while the next one loads — avoids the
    // "all cards disappear briefly when paginating" jank.
    placeholderData: (prev) => prev,
  });
}

export { PAGE_SIZE };
