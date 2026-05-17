import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  /** Optional delta (e.g. "+12%" or "−3"). Color hint via `deltaTone`. */
  delta?: ReactNode;
  deltaTone?: "neutral" | "positive" | "negative";
  /** Auxiliary text under the value (e.g. "vs. last refresh"). */
  hint?: ReactNode;
  className?: string;
  /** Add an icon to the left of the label. */
  icon?: ReactNode;
}

/**
 * Stat — big number + label, optionally with a delta arrow. Used on
 * Dashboard and zip detail headers. Plan §6 primitive.
 */
export function Stat({ label, value, delta, deltaTone = "neutral", hint, className, icon }: StatProps) {
  const tone = {
    neutral: "text-fg-muted",
    positive: "text-success",
    negative: "text-danger",
  }[deltaTone];

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-fg-muted">
        {icon && <span className="shrink-0">{icon}</span>}
        <span>{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold tabular-nums text-fg">{value}</span>
        {delta !== undefined && delta !== null && (
          <span className={cn("text-xs font-medium tabular-nums", tone)}>{delta}</span>
        )}
      </div>
      {hint && <div className="text-xs text-fg-subtle">{hint}</div>}
    </div>
  );
}
