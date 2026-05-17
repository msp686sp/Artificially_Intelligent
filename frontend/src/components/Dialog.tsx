import { Dialog as HDialog, Transition, TransitionChild } from "@headlessui/react";
import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Back-compat alias for ``footer`` — agent 5's confirmation dialogs
   * pass action buttons via this prop. */
  actions?: ReactNode;
  /** Visual width. Defaults to md (max-w-md). */
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZE_MAP = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-2xl",
};

/**
 * Dialog — modal dialog wrapper around Headless UI's Dialog primitive.
 * Headless gives us focus trap + esc-to-close + scroll lock for free.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  actions,
  size = "md",
  className,
}: DialogProps) {
  const resolvedFooter = footer ?? actions;
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

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 sm:items-center">
            <TransitionChild
              as={Fragment}
              enter="ease-out duration-150"
              enterFrom="opacity-0 translate-y-4 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-100"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:scale-95"
            >
              <HDialog.Panel
                className={cn(
                  "w-full rounded-xl border border-border bg-bg-panel p-5 text-fg shadow-xl",
                  SIZE_MAP[size],
                  className,
                )}
              >
                {(title || description) && (
                  <div className="mb-3">
                    {title && (
                      <HDialog.Title className="text-base font-semibold">{title}</HDialog.Title>
                    )}
                    {description && (
                      <HDialog.Description className="mt-1 text-sm text-fg-muted">
                        {description}
                      </HDialog.Description>
                    )}
                  </div>
                )}
                <div className="text-sm">{children}</div>
                {resolvedFooter && (
                  <div className="mt-5 flex justify-end gap-2">{resolvedFooter}</div>
                )}
              </HDialog.Panel>
            </TransitionChild>
          </div>
        </div>
      </HDialog>
    </Transition>
  );
}
