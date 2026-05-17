import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface KbdHintProps {
  children: ReactNode;
  className?: string;
}

/** Inline keyboard-shortcut hint (e.g. "⌘K" on a search bar). */
export function KbdHint({ children, className }: KbdHintProps) {
  return (
    <kbd
      className={cn(
        "inline-flex items-center rounded border border-border bg-bg-subtle px-1.5 py-0.5 font-mono text-[10px] font-medium text-fg-muted",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
