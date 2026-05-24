"use client";

/**
 * Top navigation bar.
 *
 * Server-Component-friendly contract: the parent (layout.tsx) reads the
 * session via `auth()` and passes it down. This component is "use client"
 * because it contains:
 *   - the user-menu dropdown (Base UI portal — client-only)
 *   - the credit badge that calls useMe() (TanStack Query — client-only)
 *   - the Buy Credits modal flow (Sprint 5)
 *
 * When signed out, the navbar shows only the app name. The sign-in CTA
 * lives on the page body (not in the navbar) so it has more visual weight.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Session } from "next-auth";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { BuyCreditsModal } from "@/components/buy-credits-modal";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { signOutAction } from "@/lib/auth/actions";
import { useMe } from "@/lib/api/use-me";

export function Navbar({ session }: { session: Session | null }) {
  const [buyOpen, setBuyOpen] = useState(false);

  // Sprint 5 return-URL handler. Stripe redirects to:
  //   /?checkout=success&session_id=cs_test_...     — payment OK
  //   /?checkout=cancel                              — user closed Checkout
  //
  // The webhook is what actually grants credits (browser redirect ≠ proof
  // of payment), but the redirect tells us when to invalidate the cached
  // balance + clean the URL so a refresh doesn't re-trigger the toast.
  // We do this once on mount and any time the URL changes.
  useCheckoutReturnHandler();

  return (
    <>
      <nav className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur sm:px-6">
        <Link href="/" className="font-semibold tracking-tight">
          img-vid-generation
        </Link>

        {session?.user && (
          <div className="flex items-center gap-3">
            <Link
              href="/history"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              History
            </Link>
            <CreditBadge onClick={() => setBuyOpen(true)} />
            <UserMenu user={session.user} />
          </div>
        )}
      </nav>
      <BuyCreditsModal open={buyOpen} onClose={() => setBuyOpen(false)} />
    </>
  );
}

function CreditBadge({ onClick }: { onClick: () => void }) {
  const { data, isLoading, isError } = useMe();

  // While loading or on error, render a placeholder pill so layout doesn't
  // jump when the data arrives.
  const label = isLoading ? "…" : isError ? "—" : data?.balance.toLocaleString();

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Credit balance: ${label}. Click to buy more.`}
      className="inline-flex h-8 cursor-pointer items-center rounded-full border bg-secondary px-3 text-xs font-medium text-secondary-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="mr-1.5 opacity-70">credits</span>
      <span className="tabular-nums">{label}</span>
    </button>
  );
}

function UserMenu({ user }: { user: NonNullable<Session["user"]> }) {
  const initial = (user.name ?? user.email ?? "?").slice(0, 1).toUpperCase();
  const router = useRouter();

  // After signOutAction clears the cookie, router.refresh() forces Server
  // Components (including this layout's <Navbar />) to re-render with the
  // now-null session. Without refresh(), staying on the same route ("/")
  // means the user sees stale UI even though the cookie is gone.
  async function handleSignOut() {
    await signOutAction();
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-full outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-ring">
        <Avatar className="h-8 w-8">
          {user.image && <AvatarImage src={user.image} alt={user.name ?? "Avatar"} />}
          <AvatarFallback>{initial}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex flex-col gap-1">
            <span className="font-medium">{user.name}</span>
            <span className="text-xs font-normal text-muted-foreground">
              {user.email}
            </span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void handleSignOut()}>
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Reads ?checkout=... from the current URL and reacts:
 *   - success → invalidate ["me"] so the new balance shows up; strip the
 *               query params from the URL so a refresh doesn't re-fire.
 *   - cancel  → just strip the params (silent).
 *
 * The actual credit grant happens server-side via the Stripe webhook, NOT
 * here. There's a small window where the user lands on success before the
 * webhook has fired — invalidating the cache then will still show the old
 * balance. A future polish would be a brief retry; for now the user can
 * just refresh after a beat.
 */
function useCheckoutReturnHandler() {
  const queryClient = useQueryClient();
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("checkout");
    if (!result) return;

    if (result === "success") {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    }
    // Strip ?checkout=... so a refresh doesn't re-trigger this. Keep any
    // other params the user might have on the URL.
    params.delete("checkout");
    params.delete("session_id");
    const nextSearch = params.toString();
    const nextUrl = window.location.pathname + (nextSearch ? `?${nextSearch}` : "");
    router.replace(nextUrl);
  }, [queryClient, router]);
}
