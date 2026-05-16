"use client";

/**
 * Shows the authenticated user's credit balance.
 *
 * Calls FastAPI's GET /me via the useMe() hook. The first call from a new
 * user also provisions their User + Profile rows in Postgres (just-in-time,
 * server-side — see apps/api/app/deps/auth.py). So this component is the
 * trigger that makes "signing in" actually create a database row.
 */

import { useMe } from "@/lib/api/use-me";

export function BalanceDisplay() {
  const { data, isLoading, isError, error } = useMe();

  if (isLoading) {
    return <p className="text-sm opacity-70">Loading balance…</p>;
  }
  if (isError) {
    return (
      <p className="text-sm text-red-500">
        Couldn&apos;t load balance: {error instanceof Error ? error.message : "unknown error"}
      </p>
    );
  }
  return (
    <p className="text-sm">
      Balance: <span className="font-medium">{data?.balance ?? 0}</span> credits
    </p>
  );
}
