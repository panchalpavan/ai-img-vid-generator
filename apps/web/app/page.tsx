import Image from "next/image";

import { auth, signIn, signOut } from "@/auth";
import { BalanceDisplay } from "./_components/balance-display";

/**
 * Home page (Server Component).
 *
 * Reads the current session on the server via `auth()`. Renders different UI
 * depending on whether the user is signed in.
 *
 * Sign-in / sign-out are Server Actions — the `"use server"` directive in
 * each inline async function tells Next.js to run it on the server when the
 * form is submitted. This keeps the client bundle small (no Auth.js client
 * code shipped) and avoids the need for a SessionProvider context.
 */
export default async function Home() {
  const session = await auth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold">img-vid-generation</h1>

      {session?.user ? (
        <SignedInView
          name={session.user.name ?? null}
          email={session.user.email ?? null}
          image={session.user.image ?? null}
        />
      ) : (
        <SignedOutView />
      )}
    </main>
  );
}

function SignedOutView() {
  return (
    <form
      action={async () => {
        "use server";
        await signIn("google", { redirectTo: "/" });
      }}
    >
      <button
        type="submit"
        className="rounded-md bg-foreground px-4 py-2 text-background hover:opacity-90"
      >
        Sign in with Google
      </button>
    </form>
  );
}

function SignedInView({
  name,
  email,
  image,
}: {
  name: string | null;
  email: string | null;
  image: string | null;
}) {
  return (
    <div className="flex flex-col items-center gap-4">
      {image && (
        <Image
          src={image}
          alt={name ?? "Profile picture"}
          width={64}
          height={64}
          className="rounded-full"
        />
      )}
      <div className="text-center">
        <p className="text-lg">{name}</p>
        <p className="text-sm opacity-70">{email}</p>
      </div>
      <BalanceDisplay />
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/" });
        }}
      >
        <button
          type="submit"
          className="rounded-md border border-foreground px-4 py-2 hover:bg-foreground hover:text-background"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
