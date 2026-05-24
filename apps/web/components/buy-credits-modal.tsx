"use client";

/**
 * Buy Credits modal (Sprint 5).
 *
 * Renders the available packs as cards. Clicking one fires a mutation
 * that creates a Stripe Checkout Session and then navigates the browser
 * to Stripe's hosted page — so this modal is *the last thing* the user
 * sees in our UI before going to Stripe.
 *
 * Plain Tailwind overlay rather than Shadcn Dialog because we don't have
 * a Dialog primitive installed yet and the dep cost (Base UI dialog) isn't
 * worth it for one modal. If we add more modals later it's worth promoting
 * to a reusable primitive.
 *
 * Accessibility:
 *   - Escape key closes (`onKeyDown` on the overlay container).
 *   - Click on the backdrop closes; click on the panel does not.
 *   - role="dialog" + aria-modal so screen readers announce it.
 */

import { Loader2, X } from "lucide-react";
import { useEffect } from "react";

import { useBillingPacks, useStartCheckout } from "@/lib/api/use-billing";
import { cn } from "@/lib/utils";

interface BuyCreditsModalProps {
  open: boolean;
  onClose: () => void;
}

export function BuyCreditsModal({ open, onClose }: BuyCreditsModalProps) {
  const packs = useBillingPacks();
  const checkout = useStartCheckout();

  // Escape closes the modal. Bound at document level so the user doesn't
  // need to have focus on the modal itself (common UX expectation).
  useEffect(() => {
    if (!open) return;
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="buy-credits-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        // stopPropagation so clicking inside the panel doesn't trigger
        // the backdrop's onClick (which would close the modal).
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl rounded-2xl border border-border bg-card p-6 shadow-xl"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 inline-flex size-8 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" />
        </button>

        <div className="mb-6">
          <h2
            id="buy-credits-title"
            className="text-xl font-semibold tracking-tight"
          >
            Buy credits
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Credits power every generation. Pick a pack — you'll be redirected
            to Stripe to complete payment.
          </p>
        </div>

        {packs.isLoading && (
          <CenteredMessage>Loading packs…</CenteredMessage>
        )}
        {(packs.isError || (packs.data && packs.data.length === 0)) && (
          <CenteredMessage tone="error">
            No credit packs are configured. Set STRIPE_PRICE_ID_* in the API
            .env and restart.
          </CenteredMessage>
        )}
        {packs.data && packs.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-3">
            {packs.data.map((pack) => (
              <PackCard
                key={pack.id}
                pack={pack}
                isBusy={checkout.isPending}
                onBuy={() => checkout.mutate(pack.id)}
              />
            ))}
          </div>
        )}

        {checkout.isError && (
          <p className="mt-4 text-sm text-destructive">
            Couldn't start checkout: {checkout.error.message}
          </p>
        )}
      </div>
    </div>
  );
}

function PackCard({
  pack,
  isBusy,
  onBuy,
}: {
  pack: { id: string; display_name: string; credits: number; price_cents: number; currency: string };
  isBusy: boolean;
  onBuy: () => void;
}) {
  // Render `$5.00` for `500` cents `USD`. Intl handles currency symbol +
  // locale-appropriate formatting (the user's browser locale, not the
  // currency's locale — which is the right default for displaying a price
  // to the visitor).
  const price = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: pack.currency.toUpperCase(),
  }).format(pack.price_cents / 100);

  return (
    <button
      type="button"
      onClick={onBuy}
      disabled={isBusy}
      className={cn(
        "group flex flex-col items-start gap-2 rounded-xl border border-border bg-background p-4 text-left transition-colors",
        "hover:border-primary hover:bg-muted/40 cursor-pointer",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      <p className="text-sm font-medium text-foreground">{pack.display_name}</p>
      <p className="text-2xl font-semibold tracking-tight">
        {pack.credits.toLocaleString()}{" "}
        <span className="text-sm font-normal text-muted-foreground">credits</span>
      </p>
      <p className="text-sm text-muted-foreground">{price}</p>
      <p className="mt-auto inline-flex items-center gap-1.5 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
        {isBusy ? <Loader2 className="size-3 animate-spin" /> : null}
        {isBusy ? "Starting checkout…" : "Buy →"}
      </p>
    </button>
  );
}

function CenteredMessage({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "error";
}) {
  return (
    <div className="flex items-center justify-center py-10 text-center">
      <p
        className={cn(
          "text-sm",
          tone === "error" ? "text-destructive" : "text-muted-foreground",
        )}
      >
        {children}
      </p>
    </div>
  );
}
