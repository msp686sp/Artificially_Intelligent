import { cn } from "@/lib/cn";

interface SkeletonProps {
  className?: string;
  /** Number of stacked rows; useful for placeholder lists/tables. */
  rows?: number;
}

/**
 * Skeleton — pulsing placeholder while data loads. Pass a Tailwind
 * width/height via className, or use the `rows` prop for a stacked
 * card-shaped placeholder.
 */
export function Skeleton({ className, rows }: SkeletonProps) {
  if (rows && rows > 1) {
    return (
      <div className="space-y-2" data-testid="skeleton-stack">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={cn("h-4 w-full", i === rows - 1 && "w-2/3")} />
        ))}
      </div>
    );
  }
  return (
    <div
      data-testid="skeleton"
      className={cn(
        "animate-pulse rounded-md bg-bg-panel/80 dark:bg-bg-panel",
        "h-4 w-full",
        className,
      )}
    />
  );
}
