/**
 * GET /api/auth/token — returns the raw Auth.js JWT to the authenticated client.
 *
 * Why this exists:
 *   The Auth.js session cookie is HttpOnly — JavaScript on the page cannot
 *   read it (security against XSS token theft). For client-side fetches to
 *   FastAPI that need `Authorization: Bearer <jwt>`, the client must obtain
 *   the JWT somehow. This server route reads the cookie (which the server
 *   CAN see) and returns it as a plain JSON response to the same authenticated
 *   client.
 *
 * Security:
 *   - The endpoint requires an authenticated session — `auth()` returns null
 *     if the cookie is missing or invalid, and we return 401.
 *   - The response is `Cache-Control: no-store` so intermediaries do not
 *     cache JWTs.
 *   - This is a same-origin endpoint; CORS is not relaxed.
 *   - The exposed JWT lives in memory on the client (e.g., a TanStack Query
 *     cache). It is NOT written to localStorage by our code.
 */

import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { auth } from "@/auth";

// Auth.js uses different cookie names depending on HTTPS context:
//   - dev (HTTP):   "authjs.session-token"
//   - prod (HTTPS): "__Secure-authjs.session-token"
const COOKIE_CANDIDATES = [
  "authjs.session-token",
  "__Secure-authjs.session-token",
];

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json(
      { error: "unauthenticated" },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }

  const cookieStore = await cookies();
  let token: string | undefined;
  for (const name of COOKIE_CANDIDATES) {
    const found = cookieStore.get(name)?.value;
    if (found) {
      token = found;
      break;
    }
  }

  if (!token) {
    // Session exists but cookie not found — odd, but be explicit about it.
    return NextResponse.json(
      { error: "session_cookie_not_found" },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }

  return NextResponse.json(
    { token },
    { headers: { "Cache-Control": "no-store" } },
  );
}
