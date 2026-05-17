import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

/** Source-status values from the manifest. Mapped to tones below. */
export type BadgeStatus = "ok" | "stale" | "error" | "never" | "neutral";

interface BadgeProps {
  tone?: BadgeTone;
  /** Convenience prop: maps directly to a tone via STATUS_TO_TONE. */
  status?: BadgeStatus;
  children: ReactNode;
  className?: string;
}

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-bg-subtle text-fg-muted border-border-subtle",
  success: "bg-success/10 text-success border-success/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  info: "bg-accent/10 text-accent border-accent/30",
};

const STATUS_TO_TONE: Record<BadgeStatus, BadgeTone> = {
  ok: "success",
  stale: "warning",
  error: "danger",
  never: "neutral",
  neutral: "neutral",
};

/** Compact pill for status/category labels. Accepts either `tone` or
 * `status` (back-compat for agent 5's source/manifest cards). */
export function Badge({ tone, status, children, className }: BadgeProps) {
  const resolved: BadgeTone = tone ?? (status ? STATUS_TO_TONE[status] : "neutral");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        TONES[resolved],
        className,
      )}
    >
      {children}
    </span>
  );
}
