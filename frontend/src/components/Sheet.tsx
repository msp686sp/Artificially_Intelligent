import { Dialog as HDialog, Transition, TransitionChild } from "@headlessui/react";
import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  side?: "left" | "right" | "bottom";
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Tailwind size class override for the panel's main dim (width or height). */
  size?: string;
  className?: string;
  /** Test id passed through to the panel. */
  "data-testid"?: string;
}

/**
 * Sheet — slide-out drawer. Used for the filter sidebar on `/rankings`
 * and for the mobile navigation panel (via <MobileNav>). Built on
 * Headless UI's Dialog primitive so it gets focus trap + esc-to-close.
 */
export function Sheet({
  open,
  onClose,
  side = "right",
  title,
  description,
  children,
  footer,
  size,
  className,
  ...rest
}: SheetProps) {
  const sideCfg = {
    left: {
      align: "items-stretch justify-start",
      panel: cn("h-full w-full max-w-xs", size),
      enterFrom: "-translate-x-full",
      enterTo: "translate-x-0",
    },
    right: {
      align: "items-stretch justify-end",
      panel: cn("h-full w-full max-w-md", size),
      enterFrom: "translate-x-full",
      enterTo: "translate-x-0",
    },
    bottom: {
      align: "items-end justify-stretch",
      panel: cn("h-auto max-h-[85vh] w-full", size),
      enterFrom: "translate-y-full",
      enterTo: "translate-y-0",
    },
  }[side];

  return (
    <Transition show={open} as={Fragment}>
      <HDialog as="div" className="relative z-50" onClose={onClose}>
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-150"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" aria-hidden />
        </TransitionChild>

        <div className={cn("fixed inset-0 flex", sideCfg.align)}>
          <TransitionChild
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom={sideCfg.enterFrom}
            enterTo={sideCfg.enterTo}
            leave="ease-in duration-150"
            leaveFrom={sideCfg.enterTo}
            leaveTo={sideCfg.enterFrom}
          >
            <HDialog.Panel
              data-testid={rest["data-testid"]}
              className={cn(
                "flex flex-col border-border bg-bg-panel text-fg shadow-xl",
                side === "bottom" ? "rounded-t-xl border-t" : "border-r border-l",
                sideCfg.panel,
                className,
              )}
            >
              {(title || description) && (
                <div className="flex items-start justify-between gap-3 border-b border-border-subtle p-4">
                  <div>
                    {title && (
                      <HDialog.Title className="text-sm font-semibold text-fg">
                        {title}
                      </HDialog.Title>
                    )}
                    {description && (
                      <HDialog.Description className="mt-1 text-xs text-fg-muted">
                        {description}
                      </HDialog.Description>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close panel"
                    className="-m-1 inline-flex min-h-touch min-w-touch items-center justify-center rounded p-2 text-fg-muted hover:text-fg"
                  >
                    ×
                  </button>
                </div>
              )}
              <div className="flex-1 overflow-y-auto p-4">{children}</div>
              {footer && (
                <div className="flex items-center justify-end gap-2 border-t border-border-subtle p-3">
                  {footer}
                </div>
              )}
            </HDialog.Panel>
          </TransitionChild>
        </div>
      </HDialog>
    </Transition>
  );
}
