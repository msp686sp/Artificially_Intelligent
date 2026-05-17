import { useEffect } from "react";
import type { PropsWithChildren, ReactNode } from "react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  actions?: ReactNode;
}

export function Dialog({
  open,
  onClose,
  title,
  actions,
  children,
}: PropsWithChildren<DialogProps>) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="dialog-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog">
        <h3>{title}</h3>
        <div>{children}</div>
        {actions && <div className="actions">{actions}</div>}
      </div>
    </div>
  );
}
