import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";

import "./globals.css";
import { auth } from "@/auth";
import { Navbar } from "@/components/navbar";
import { QueryProvider } from "@/lib/query/provider";
import { ThemeProvider } from "@/lib/theme/provider";

// Geist Mono is kept for any monospaced contexts (code blocks, IDs, etc.).
// The body/sans font uses the system stack defined in globals.css — see
// `--font-sans` there. On macOS/iOS that resolves to SF Pro automatically.
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "img-vid-generation",
  description: "AI image and video generation",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await auth();

  return (
    <html
      lang="en"
      className={`${geistMono.variable} h-full antialiased`}
      // next-themes mutates className before hydration; suppress mismatch.
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider>
          <QueryProvider>
            <Navbar session={session} />
            <main className="flex-1">{children}</main>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
