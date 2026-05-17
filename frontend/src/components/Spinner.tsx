import { cn } from "@/lib/cn";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

/**
 * Spinner — minimal CSS spinner. Use for inline loading indicators
 * (buttons, table cells). For full-page loaders use Skeleton.
 */
export function Spinner({ size = "md", className, label = "Loading" }: SpinnerProps) {
  const dims = { sm: "h-3 w-3 border", md: "h-4 w-4 border-2", lg: "h-6 w-6 border-2" }[size];
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        "inline-block animate-spin rounded-full border-current border-r-transparent",
        dims,
        className,
      )}
    />
  );
}
