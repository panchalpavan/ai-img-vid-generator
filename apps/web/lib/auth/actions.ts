"use server";

/**
 * Server Actions for Auth.js operations.
 *
 * These wrap Auth.js's server-side `signIn` / `signOut` helpers so Client
 * Components (like the user dropdown menu) can call them. Server Actions
 * are RPC-style: the client receives a function reference; calling it
 * triggers an HTTP request that runs the body on the server.
 */

import { signIn, signOut } from "@/auth";

export async function signInWithGoogleAction() {
  await signIn("google", { redirectTo: "/" });
}

export async function signOutAction() {
  await signOut({ redirectTo: "/" });
}
