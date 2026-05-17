import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// Recharts' ResponsiveContainer needs an actual size in jsdom.
// Mock ResizeObserver so charts can render in tests.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// jsdom is missing ResizeObserver
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverMock;

// Recharts' ResponsiveContainer warns about width=0 in jsdom. Patch
// getBoundingClientRect / offsetWidth so charts get a non-zero size in tests.
Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  get(): number {
    return 400;
  },
});
Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  get(): number {
    return 400;
  },
});

// Also stub matchMedia (sometimes needed by responsive primitives)
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
