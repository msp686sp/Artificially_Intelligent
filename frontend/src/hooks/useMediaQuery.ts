import { useEffect, useState } from "react";

/**
 * useMediaQuery — listen for a CSS media query and re-render when it
 * flips. SSR-safe: defaults to `false` until the effect runs.
 *
 * @example
 *   const isDesktop = useMediaQuery("(min-width: 1024px)");
 */
export function useMediaQuery(query: string): boolean {
  const getMatch = () => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(query).matches;
  };
  const [matches, setMatches] = useState<boolean>(getMatch);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    const update = () => setMatches(mql.matches);
    update();
    // Both for old Safari and modern browsers.
    if (mql.addEventListener) {
      mql.addEventListener("change", update);
      return () => mql.removeEventListener("change", update);
    }
    mql.addListener(update);
    return () => mql.removeListener(update);
  }, [query]);

  return matches;
}

// Convenience breakpoint hooks aligned with Tailwind defaults.
export const useIsMobile = () => !useMediaQuery("(min-width: 640px)");
export const useIsDesktop = () => useMediaQuery("(min-width: 1024px)");
