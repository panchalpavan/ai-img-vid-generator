"use client";

/**
 * Top navigation bar.
 *
 * Server-Component-friendly contract: the parent (layout.tsx) reads the
 * session via `auth()` and passes it down. This component is "use client"
 * because it contains:
 *   - the user-menu dropdown (Radix UI portal — client-only)
 *   - the credit badge that calls useMe() (TanStack Query — client-only)
 *
 * When signed out, the navbar shows only the app name. The sign-in CTA
 * lives on the page body (not in the navbar) so it has more visual weight.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Session } from "next-auth";

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
  return (
    <nav className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur sm:px-6">
      <Link href="/" className="font-semibold tracking-tight">
        img-vid-generation
      </Link>

      {session?.user && (
        <div className="flex items-center gap-3">
          <CreditBadge />
          <UserMenu user={session.user} />
        </div>
      )}
    </nav>
  );
}

function CreditBadge() {
  const { data, isLoading, isError } = useMe();

  // While loading or on error, render a placeholder pill so layout doesn't
  // jump when the data arrives.
  const label = isLoading ? "…" : isError ? "—" : data?.balance.toLocaleString();

  return (
    <span
      className="inline-flex h-8 items-center rounded-full border bg-secondary px-3 text-xs font-medium text-secondary-foreground"
      aria-label={`Credit balance: ${label}`}
    >
      <span className="mr-1.5 opacity-70">credits</span>
      <span className="tabular-nums">{label}</span>
    </span>
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
