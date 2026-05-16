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
 *
 * JWT FORMAT OVERRIDE:
 * By default, Auth.js v5 encrypts session tokens as JWE. We override the
 * encode/decode to produce HS256-signed JWS instead — that's the format
 * FastAPI verifies with PyJWT (see apps/api/app/deps/auth.py). Same secret,
 * same algorithm on both ends.
 */

import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { SignJWT, jwtVerify, type JWTPayload } from "jose";

const HS256 = "HS256";
const TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 30; // 30 days, matches Auth.js default

function secretToBytes(secret: string | Uint8Array | (string | Uint8Array)[]): Uint8Array {
  // Auth.js may pass a string, a Uint8Array, or an array of secrets (for rotation).
  // We always use the first one as bytes.
  const single = Array.isArray(secret) ? secret[0] : secret;
  if (single instanceof Uint8Array) return single;
  return new TextEncoder().encode(single as string);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt", maxAge: TOKEN_LIFETIME_SECONDS },
  jwt: {
    async encode({ token, secret }) {
      if (!token) throw new Error("encode: missing token payload");
      return await new SignJWT(token as JWTPayload)
        .setProtectedHeader({ alg: HS256 })
        .setIssuedAt()
        .setExpirationTime(`${TOKEN_LIFETIME_SECONDS}s`)
        .sign(secretToBytes(secret));
    },
    async decode({ token, secret }) {
      if (!token) return null;
      const { payload } = await jwtVerify(token, secretToBytes(secret), {
        algorithms: [HS256],
      });
      return payload;
    },
  },
});
