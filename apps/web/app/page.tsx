import { auth } from "@/auth";
import { GenerationView } from "@/components/generation-view";
import { Button } from "@/components/ui/button";
import { signInWithGoogleAction } from "@/lib/auth/actions";

/**
 * Home page (Server Component).
 *
 * The navbar (in layout.tsx) handles the signed-in state — avatar menu,
 * credit badge. This page just shows a sign-in CTA when the user is
 * unauthenticated, or a placeholder welcome when they are. Subsequent
 * sprints will replace the welcome with the generation form (Sprint 2).
 */
export default async function Home() {
  const session = await auth();

  if (!session?.user) {
    return (
      <section className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-6 p-8 text-center">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Welcome to img-vid-generation
          </h1>
          <p className="text-muted-foreground">
            Generate images and videos with AI. Sign in to get started.
          </p>
        </div>
        <form action={signInWithGoogleAction}>
          <Button type="submit" size="lg">
            Sign in with Google
          </Button>
        </form>
      </section>
    );
  }

  return <GenerationView />;
}
