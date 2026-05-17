import {
  Dialog as HuiDialog,
  DialogPanel,
  DialogTitle,
  Transition,
  TransitionChild,
} from "@headlessui/react";
import { Fragment, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Minimal in-agent UI primitives so my routes are self-sufficient. fe-shell
 * (agent 4) owns the production design system; on merge those will replace
 * these. The API mirrors what agent 4 is expected to ship.
 */

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-bg-subtle bg-bg-panel p-4 shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  compact?: boolean;
}

export function Button({
  variant = "secondary",
  compact,
  className,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50";
  const variants: Record<ButtonVariant, string> = {
    primary: "bg-accent text-white hover:bg-accent-hover",
    secondary: "bg-bg-subtle text-fg hover:bg-bg-panel border border-bg-subtle",
    ghost: "text-fg-muted hover:bg-bg-subtle hover:text-fg",
    danger: "bg-danger text-white hover:opacity-90",
  };
  return (
    <button
      className={cn(base, variants[variant], compact && "compact", className)}
      {...props}
    />
  );
}

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  className,
}: DialogProps) {
  return (
    <Transition show={open} as={Fragment}>
      <HuiDialog as="div" className="relative z-50" onClose={onClose}>
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-150"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60" aria-hidden="true" />
        </TransitionChild>
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as={Fragment}
              enter="ease-out duration-150"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-100"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <DialogPanel
                className={cn(
                  "w-full max-w-lg rounded-xl bg-bg-panel p-5 shadow-xl",
                  className,
                )}
              >
                {title && (
                  <DialogTitle className="text-lg font-semibold">
                    {title}
                  </DialogTitle>
                )}
                <div className="mt-3 text-sm text-fg">{children}</div>
                {footer && (
                  <div className="mt-5 flex justify-end gap-2">{footer}</div>
                )}
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </HuiDialog>
    </Transition>
  );
}

export function Pill({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: "default" | "success" | "warning" | "danger" | "accent";
  className?: string;
}) {
  const tones: Record<string, string> = {
    default: "bg-bg-subtle text-fg-muted",
    success: "bg-success/20 text-success",
    warning: "bg-warning/20 text-warning",
    danger: "bg-danger/20 text-danger",
    accent: "bg-accent/20 text-accent",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-fg-muted border-t-transparent",
        className,
      )}
    />
  );
}
