/**
 * Thin typed fetch wrapper for calling apps/api.
 *
 * Two responsibilities:
 *   1. Attach the Auth.js JWT as `Authorization: Bearer <jwt>` to every call.
 *   2. Throw on non-2xx responses with a useful error body.
 *
 * The JWT is fetched from `/api/auth/token` (same-origin Next.js route that
 * reads the HttpOnly cookie server-side and returns it).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API ${status}: ${JSON.stringify(body)}`);
    this.name = "ApiError";
  }
}

async function fetchJwt(): Promise<string> {
  const res = await fetch("/api/auth/token", { credentials: "include" });
  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null));
  }
  const json = (await res.json()) as { token: string };
  return json.token;
}

/**
 * GET <api>/<path> with the user's JWT attached.
 * Returns the parsed JSON response, typed by the caller.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const jwt = await fetchJwt();
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${jwt}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null));
  }
  return (await res.json()) as T;
}

export { ApiError };
