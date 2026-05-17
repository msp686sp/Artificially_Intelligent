import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  fullWidth?: boolean;
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover disabled:bg-accent/40 disabled:cursor-not-allowed",
  secondary:
    "bg-bg-panel text-fg border border-border hover:border-fg-muted disabled:opacity-50 disabled:cursor-not-allowed",
  ghost: "bg-transparent text-fg hover:bg-bg-panel disabled:opacity-50 disabled:cursor-not-allowed",
  danger:
    "bg-danger text-white hover:bg-danger/85 disabled:bg-danger/40 disabled:cursor-not-allowed",
};

const SIZES: Record<ButtonSize, string> = {
  // All sizes maintain a 44px minimum height for touch.
  sm: "h-9 min-h-touch px-3 text-sm gap-1.5",
  md: "h-11 min-h-touch px-4 text-sm gap-2",
  lg: "h-12 min-h-touch px-5 text-base gap-2",
};

/**
 * Button — the canonical primary action element. All variants meet a
 * 44px minimum tap target so the same component works on phones.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading,
    leftIcon,
    rightIcon,
    fullWidth,
    className,
    disabled,
    children,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors",
        "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
        VARIANTS[variant],
        SIZES[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner size="sm" /> : leftIcon}
      <span className="inline-flex items-center">{children}</span>
      {!loading && rightIcon}
    </button>
  );
});
