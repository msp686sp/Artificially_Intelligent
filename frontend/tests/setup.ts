import "@testing-library/jest-dom/vitest";

// jsdom lacks matchMedia; the components that depend on it (Theme,
// useMediaQuery) treat a missing API as "no match", but adding a no-op
// stub keeps `mql.addEventListener` etc. happy.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
