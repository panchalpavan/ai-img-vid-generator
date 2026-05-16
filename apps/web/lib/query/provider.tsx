"use client";

/**
 * Wraps the app in a TanStack Query context.
 *
 * Why this is a Client Component (`"use client"`):
 *   QueryClient holds an in-memory cache and uses React Context. Both are
 *   client-only concerns. The provider must live in a Client Component so
 *   React knows to ship it to the browser.
 *
 * Why we create the QueryClient inside a useState initializer:
 *   If we created it at module top-level, the SAME client would be shared
 *   across users on the server during SSR — leaking one user's data to the
 *   next. `useState(() => new QueryClient())` creates one client per
 *   browser session.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, type ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Don't refetch on every focus — annoying for dev.
            refetchOnWindowFocus: false,
            // Keep data "fresh" for 30s. Caller can override per-query.
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      {children}
      {/* Devtools panel: only included in dev builds (tree-shaken in prod). */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
