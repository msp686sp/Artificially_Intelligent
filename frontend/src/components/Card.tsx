import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  /** Tighter padding for dense dashboards. */
  dense?: boolean;
  /** Removes the inner padding so the caller controls spacing (e.g. for tables). */
  flush?: boolean;
  /** Back-compat alias — `padded={false}` ⇒ no inner padding. */
  padded?: boolean;
  /** Convenience: render a CardHeader at the top of the card. */
  title?: ReactNode;
  /** Header description (only used when `title` is also set). */
  description?: ReactNode;
  /** Header action element (only used when `title` is also set). */
  action?: ReactNode;
  /** Back-compat alias for ``action``. */
  actions?: ReactNode;
}

/**
 * Card — the panel primitive (`bg-bg-panel rounded-xl shadow-sm p-4`)
 * defined in plan §6. Every dashboard stat, source row, and chart
 * sits inside one.
 */
export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, dense, flush, padded, children, title, description, action, actions, ...rest },
  ref,
) {
  const headerAction = action ?? actions;
  const isFlush = flush ?? (padded === false);
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border border-border-subtle bg-bg-panel text-fg shadow-sm",
        !isFlush && (dense ? "p-3" : "p-4"),
        className,
      )}
      {...rest}
    >
      {title && <CardHeader title={title} description={description} action={headerAction} />}
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
