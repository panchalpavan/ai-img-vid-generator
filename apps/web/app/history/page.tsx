import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { GenerationsGallery } from "@/components/generations-gallery";

/**
 * /history — past generations gallery.
 *
 * Auth-gated server side. If the user isn't signed in we redirect to "/"
 * rather than rendering a sign-in CTA — the gallery's empty without auth
 * anyway, and the home page already has the sign-in flow.
 */
export default async function HistoryPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/");
  }
  return <GenerationsGallery />;
}
