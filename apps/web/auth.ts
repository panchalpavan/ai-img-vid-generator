/**
 * Auth.js (next-auth v5) central configuration.
 *
 * Exports:
 *   - handlers: HTTP route handlers for /api/auth/* — wired in app/api/auth/[...nextauth]/route.ts
 *   - auth:     Server-side helper to read the current session — `const session = await auth()`
 *   - signIn:   Server Action to initiate sign-in (`await signIn("google")`)
 *   - signOut:  Server Action to sign the user out
 *
 * Env vars auto-detected by Auth.js v5:
 *   - AUTH_SECRET        — signs the session token
 *   - AUTH_URL           — base URL for OAuth callbacks
 *   - AUTH_GOOGLE_ID     — Google OAuth Client ID
 *   - AUTH_GOOGLE_SECRET — Google OAuth Client Secret
 *
 * Session strategy is JWT (not database) — see ADR-0009. The signing secret
 * (AUTH_SECRET here) MUST match JWT_SECRET in apps/api/.env so that FastAPI
 * can verify tokens issued by Auth.js.
 */

import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
});
