import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Tighter padding for dense dashboards. */
  dense?: boolean;
  /** Removes the inner padding so the caller controls spacing (e.g. for tables). */
  flush?: boolean;
}

/**
 * Card — the panel primitive (`bg-bg-panel rounded-xl shadow-sm p-4`)
 * defined in plan §6. Every dashboard stat, source row, and chart
 * sits inside one.
 */
export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, dense, flush, children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border border-border-subtle bg-bg-panel text-fg shadow-sm",
        !flush && (dense ? "p-3" : "p-4"),
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
});

interface CardSectionProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  action?: ReactNode;
  description?: ReactNode;
}

/** Section header inside a Card — title + optional action button. */
export function CardHeader({ title, action, description, className, ...rest }: CardSectionProps) {
  return (
    <div className={cn("mb-3 flex items-start justify-between gap-3", className)} {...rest}>
      <div>
        {title && <h3 className="text-sm font-semibold text-fg">{title}</h3>}
        {description && <p className="mt-1 text-xs text-fg-muted">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
