import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  /** Visual placement. */
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

/**
 * Tooltip — lightweight, hover/focus-revealed text. We use a CSS-only
 * approach so it works with keyboard focus and doesn't require Floating
 * UI overhead. For mobile (no hover), the tooltip surfaces on
 * tap/focus.
 */
export function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  const sideClasses = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  }[side];

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      aria-describedby={open ? id : undefined}
    >
      {children}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border bg-bg-subtle px-2 py-1 text-xs text-fg shadow-md",
            sideClasses,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
