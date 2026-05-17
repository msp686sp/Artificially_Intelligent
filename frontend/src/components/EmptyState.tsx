import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface EmptyStateProps {
  /** Page name — shows up in the title. */
  pageName?: string;
  /** Which agent owns this page (e.g. "agent 5/6/7"). */
  ownedBy?: string;
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}

/**
 * EmptyState — placeholder used in three contexts:
 *
 * 1. **Route placeholders** (this agent owns the shell, not the page
 *    content). Other agents replace the route component with their
 *    real page. Until then, EmptyState shows "owned by agent X".
 * 2. **Empty result sets** — "No rankings match these filters."
 * 3. **Not-yet-loaded warehouse** — "Run `make init` first."
 */
export function EmptyState({
  pageName,
  ownedBy,
  title,
  description,
  action,
  icon,
  className,
}: EmptyStateProps) {
  const resolvedTitle =
    title ?? (pageName ? `${pageName} — placeholder` : "Nothing here yet");
  const resolvedDescription =
    description ??
    (ownedBy
      ? `This page is owned by ${ownedBy}. The shell is wired up; the route content will land when that agent integrates.`
      : "No content to show.");

  return (
    <div
      className={cn(
        "flex min-h-[40vh] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-bg-panel/30 px-6 py-12 text-center",
        className,
      )}
      data-testid="empty-state"
      data-page={pageName}
    >
      {icon && <div className="text-fg-muted">{icon}</div>}
      <h2 className="text-lg font-semibold text-fg">{resolvedTitle}</h2>
      <p className="max-w-md text-sm text-fg-muted">{resolvedDescription}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
