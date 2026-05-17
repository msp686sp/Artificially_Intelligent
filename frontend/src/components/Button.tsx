import { forwardRef } from "react";
import { cx } from "../lib/cx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANT_CLS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover",
  secondary: "bg-bg-panel text-fg hover:bg-bg-subtle",
  ghost: "text-fg hover:bg-bg-panel",
  danger: "bg-danger text-white hover:bg-danger/90",
};
const SIZE_CLS: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      {...rest}
      disabled={disabled}
      className={cx(
        "touch-target inline-flex items-center justify-center gap-1.5 rounded-md font-medium",
        "transition-colors focus:outline-none focus:ring-2 focus:ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT_CLS[variant],
        SIZE_CLS[size],
        className,
      )}
    />
  );
});

export default Button;
