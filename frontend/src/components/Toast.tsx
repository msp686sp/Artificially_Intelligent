import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import type { PropsWithChildren, ReactNode } from "react";

export type ToastKind = "info" | "success" | "error";

interface ToastEntry {
  id: number;
  kind: ToastKind;
  message: ReactNode;
}

interface ToastContextValue {
  push: (message: ReactNode, kind?: ToastKind) => void;
  success: (message: ReactNode) => void;
  error: (message: ReactNode) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: ReactNode, kind: ToastKind = "info") => {
      const id = nextId.current++;
      setToasts((cur) => [...cur, { id, kind, message }]);
      setTimeout(() => remove(id), 6000);
    },
    [remove],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      push,
      success: (m) => push(m, "success"),
      error: (m) => push(m, "error"),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-host" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fallback so components don't crash if rendered without provider
    // (e.g. tests). Logs to console instead.
    return {
      push: (m) => {
        if (typeof console !== "undefined") console.log("[toast]", m);
      },
      success: (m) => {
        if (typeof console !== "undefined") console.log("[toast.success]", m);
      },
      error: (m) => {
        if (typeof console !== "undefined") console.warn("[toast.error]", m);
      },
    };
  }
  return ctx;
}
