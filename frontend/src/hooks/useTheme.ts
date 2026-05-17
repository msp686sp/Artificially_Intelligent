import { useCallback, useContext } from "react";
import { ThemeContext, type Theme } from "@/layout/ThemeProvider";

export type { Theme };

/**
 * useTheme — read + set the active theme. Bound to <ThemeProvider>;
 * calling outside of one throws (loud failure beats silent bug).
 */
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  const { theme, setTheme, resolved } = ctx;
  const toggle = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);
  return { theme, setTheme, resolved, toggle };
}
