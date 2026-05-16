"use client";

/**
 * Theme provider — follows OS preference by default, with infrastructure
 * ready for a future user-facing theme toggle.
 *
 * `defaultTheme="system"` makes next-themes read `prefers-color-scheme` and
 * apply the `dark` class to <html> accordingly. `enableSystem` ensures the
 * toggle path is open for later.
 *
 * `attribute="class"` matches Shadcn's `@custom-variant dark (&:is(.dark *))`
 * convention in globals.css — dark mode activates via the class, not via a
 * media query.
 *
 * `disableTransitionOnChange` prevents a flicker when the theme switches.
 */

import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes";

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
