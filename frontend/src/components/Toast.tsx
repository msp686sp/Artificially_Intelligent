import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { cx } from "../lib/cx";

type ToastTone = "info" | "success" | "danger";
interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastContextValue {
  push: (message: string, tone?: ToastTone) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((message: string, tone: ToastTone = "info") => {
    const id = nextId++;
    setItems((prev) => [...prev, { id, tone, message }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);
  const value = useMemo(() => ({ push }), [push]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cx(
              "pointer-events-auto min-w-[200px] rounded-lg border px-3 py-2 text-sm shadow-lg",
              t.tone === "success" && "border-success/40 bg-success/20 text-success",
              t.tone === "danger" && "border-danger/40 bg-danger/20 text-danger",
              t.tone === "info" && "border-accent/40 bg-accent/20 text-accent",
            )}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  // Tolerate consumption without a provider so individual route tests still work.
  return ctx ?? { push: (msg, tone) => console.warn(`[toast:${tone ?? "info"}] ${msg}`) };
}

// Stable export used by tests to reset the auto-incrementing id between specs.
export function __resetToastIds() {
  nextId = 1;
}

// Hint to RR consumers
export { ToastContext };

// Mount the provider at app root so individual pages can push toasts without
// extra plumbing.
export function withToasts<P extends object>(Inner: React.ComponentType<P>) {
  return function Wrapped(props: P) {
    return (
      <ToastProvider>
        <Inner {...props} />
      </ToastProvider>
    );
  };
}

// Helper so we render an inert version on server / test envs without leaking timers.
export function _useFlush() {
  const ctx = useContext(ToastContext);
  useEffect(() => {
    // no-op for now; reserved.
    return () => undefined;
  }, [ctx]);
}
