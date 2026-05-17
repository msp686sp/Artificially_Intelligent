import { cx } from "../lib/cx";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padded?: boolean;
}

/**
 * Minimal Card primitive while fe-shell ships the canonical version.
 * Matches the design tokens in `tailwind.config.ts`.
 */
export function Card({ className, padded = true, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={cx(
        "rounded-xl border border-bg-panel bg-bg-panel shadow-sm",
        padded && "p-4",
        className,
      )}
    />
  );
}

export default Card;
