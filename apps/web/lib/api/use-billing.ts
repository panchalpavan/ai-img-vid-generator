"use client";

/**
 * Billing hooks (Sprint 5).
 *
 *   - useBillingPacks()    — query: list available credit packs
 *   - useStartCheckout()   — mutation: create a Stripe Checkout Session and
 *                            navigate the browser to it
 *
 * Why navigation lives inside the hook (not the caller): Stripe-hosted
 * checkout is a full-page redirect by design. After it finishes the user
 * comes back to our `success_url`, not to a callback inside the SPA.
 * Embedding `window.location.href = ...` in the success handler keeps the
 * "click Buy → end up on Stripe" flow in one place.
 */

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiGetPublic, apiPost } from "./client";
import type {
  CheckoutRequest,
  CheckoutResponse,
  PackResponse,
} from "./types";

const PACKS_QUERY_KEY = ["billing", "packs"] as const;

/** List the available credit packs (public — no auth needed). */
export function useBillingPacks() {
  return useQuery<PackResponse[], Error>({
    queryKey: PACKS_QUERY_KEY,
    queryFn: () => apiGetPublic<PackResponse[]>("/billing/packs"),
    // The catalog rarely changes within a session. Skip background
    // refetches that would otherwise re-fire on every focus.
    staleTime: 5 * 60 * 1000,
  });
}

/** Start a checkout flow: hits /billing/checkout, then redirects the browser
 * to Stripe's hosted page.
 *
 * The redirect is `window.location.href = url` rather than `router.push(url)`
 * because Stripe is a different origin — Next.js router won't navigate
 * outside the app.
 */
export function useStartCheckout() {
  return useMutation<CheckoutResponse, Error, string>({
    mutationFn: async (packId) => {
      const body: CheckoutRequest = { pack_id: packId };
      const res = await apiPost<CheckoutRequest, CheckoutResponse>(
        "/billing/checkout",
        body,
      );
      return res;
    },
    onSuccess: (data) => {
      window.location.href = data.checkout_url;
    },
  });
}
