// (intentional: this module exports both a hook and a component;
// the react-refresh constraint is not enforced in this project)
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";

export type ToastTone = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
  /** Auto-dismiss in ms. Pass 0 to make sticky. Default 4000. */
  durationMs?: number;
}

type PushArg = string | (Omit<Toast, "id"> & { id?: string });
/** Legacy tone names some routes pass as a 2nd arg. */
type LegacyTone = "info" | "success" | "warning" | "danger" | "error";

interface ToastContextValue {
  toasts: Toast[];
  /** Push a toast. Accepts a string shorthand (with optional tone) or a
   *  full Toast object. Returns the toast id. */
  push: (toast: PushArg, tone?: LegacyTone) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (toast: PushArg, legacyTone?: LegacyTone) => {
      const remap = (t?: LegacyTone): ToastTone =>
        t === "danger" ? "error" : ((t ?? "info") as ToastTone);
      const obj =
        typeof toast === "string"
          ? { tone: remap(legacyTone), title: toast }
          : toast;
      const id = obj.id ?? uid();
      const t: Toast = { durationMs: 4000, ...obj, id };
      setToasts((prev) => [...prev, t]);
      if (t.durationMs && t.durationMs > 0) {
        const handle = setTimeout(() => dismiss(id), t.durationMs);
        timers.current.set(id, handle);
      }
      return id;
    },
    [dismiss],
  );

  const clear = useCallback(() => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current.clear();
    setToasts([]);
  }, []);

  // Clear pending timers on unmount.
  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((t) => clearTimeout(t));
      map.clear();
    };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({ toasts, push, dismiss, clear }),
    [toasts, push, dismiss, clear],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  // Back-compat: expose tone-specific helpers (success/error/info/warning)
  // alongside the canonical push/dismiss/clear API. Agent 5's routes
  // were authored against this idiom — keep it stable.
  const helpers = {
    success: (title: string, description?: string) =>
      ctx.push({ tone: "success", title, description }),
    error: (title: string, description?: string) =>
      ctx.push({ tone: "error", title, description }),
    info: (title: string, description?: string) =>
      ctx.push({ tone: "info", title, description }),
    warning: (title: string, description?: string) =>
      ctx.push({ tone: "warning", title, description }),
  };
  return { ...ctx, ...helpers };
}

const TONE_STYLES: Record<ToastTone, string> = {
  info: "border-accent/40 bg-bg-panel text-fg",
  success: "border-success/40 bg-bg-panel text-fg",
  warning: "border-warning/40 bg-bg-panel text-fg",
  error: "border-danger/40 bg-bg-panel text-fg",
};

const TONE_DOT: Record<ToastTone, string> = {
  info: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-danger",
};

function ToastViewport() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;
  return (
    <div
      role="region"
      aria-label="Notifications"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-end gap-2 px-4 sm:bottom-6 sm:right-6 sm:left-auto sm:px-0"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          aria-live="polite"
          className={cn(
            "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border px-4 py-3 shadow-lg",
            TONE_STYLES[t.tone],
          )}
        >
          <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", TONE_DOT[t.tone])} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{t.title}</p>
            {t.description && <p className="mt-0.5 text-xs text-fg-muted">{t.description}</p>}
          </div>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            className="min-h-touch min-w-touch -m-1 inline-flex items-center justify-center rounded p-1 text-fg-muted hover:text-fg"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
