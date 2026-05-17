// (intentional: this module exports both a hook and a component)
import { createContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "dark" | "light" | "auto";

export interface ThemeContextValue {
  theme: Theme;
  resolved: "dark" | "light";
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "rental.gooey.theme";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "dark" || raw === "light" || raw === "auto") return raw;
  } catch {
    /* ignore */
  }
  return "dark";
}

function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme !== "auto") return theme;
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

interface ThemeProviderProps {
  children: ReactNode;
  /** Override the initial theme — useful for tests and Storybook. */
  defaultTheme?: Theme;
}

/**
 * ThemeProvider — owns the dark/light toggle. Persists to localStorage
 * and applies the `dark` class on <html> so Tailwind's `dark:` variant
 * works everywhere. Dark is the default (developer-tool convention).
 */
export function ThemeProvider({ children, defaultTheme }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => defaultTheme ?? readStoredTheme());
  const [systemDark, setSystemDark] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  // Keep system preference in sync while in "auto".
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    if (mql.addEventListener) {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    mql.addListener(onChange);
    return () => mql.removeListener(onChange);
  }, []);

  const resolved: "dark" | "light" = useMemo(() => {
    if (theme === "auto") return systemDark ? "dark" : "light";
    return theme;
  }, [theme, systemDark]);

  // Apply class to <html>.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (resolved === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [resolved]);

  // Persist.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolved, setTheme: setThemeState }),
    [theme, resolved],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

// Re-export the consumer hook for convenience.
export { useTheme } from "@/hooks/useTheme";

// Note: `resolveTheme` is exported only for unit testing.
export { resolveTheme };

// Mobile bottom-nav opt-out toggle. Settings page reads/writes this.
const MOBILE_NAV_KEY = "rental.gooey.mobileNav";

export function getMobileNavEnabled(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = window.localStorage.getItem(MOBILE_NAV_KEY);
    return raw === null ? true : raw === "1";
  } catch {
    return true;
  }
}

export function setMobileNavEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(MOBILE_NAV_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore */
  }
}
