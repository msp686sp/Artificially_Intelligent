import { cx } from "../lib/cx";

type Tone = "neutral" | "success" | "warning" | "danger" | "accent";

const TONE_CLS: Record<Tone, string> = {
  neutral: "bg-bg-subtle text-fg-muted ring-1 ring-inset ring-bg-panel",
  success: "bg-success/15 text-success ring-1 ring-inset ring-success/30",
  warning: "bg-warning/15 text-warning ring-1 ring-inset ring-warning/30",
  danger: "bg-danger/15 text-danger ring-1 ring-inset ring-danger/30",
  accent: "bg-accent/15 text-accent ring-1 ring-inset ring-accent/30",
};

export interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Chip({ className, tone = "neutral", ...rest }: ChipProps) {
  return (
    <span
      {...rest}
      className={cx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONE_CLS[tone],
        className,
      )}
    />
  );
}

export default Chip;
