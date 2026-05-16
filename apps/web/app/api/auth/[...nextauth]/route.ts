/**
 * Catch-all OAuth route — handles /api/auth/signin, /api/auth/callback/google,
 * /api/auth/session, /api/auth/csrf, /api/auth/signout, etc.
 *
 * Auth.js builds these handlers from the config in `auth.ts`; we just re-export
 * them here so Next.js's App Router picks them up at the right URL.
 */

import { handlers } from "@/auth";

export const { GET, POST } = handlers;
