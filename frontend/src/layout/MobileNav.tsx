import { NavLink } from "react-router-dom";
import { Sheet } from "@/components/Sheet";
import { BOTTOM_NAV_ITEMS, NAV_ITEMS } from "./navConfig";
import { cn } from "@/lib/cn";

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

/**
 * MobileNav — two surfaces:
 *
 * 1. A slide-out **drawer** triggered by the topbar hamburger,
 *    containing the full nav list (same items as the desktop sidebar).
 * 2. A fixed **bottom bar** with the 5 most-used routes (always
 *    visible on < sm so primary navigation is one tap away).
 *
 * Both surfaces use the same path values, so React Router stays the
 * single source of truth.
 */
export function MobileNav({ open, onClose }: MobileNavProps) {
  return (
    <>
      <Sheet
        open={open}
        onClose={onClose}
        side="left"
        title="Navigation"
        data-testid="mobile-nav-sheet"
      >
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-touch items-center gap-3 rounded-md px-3 text-sm transition-colors",
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-fg-muted hover:bg-bg-subtle hover:text-fg",
                  )
                }
              >
                <span
                  aria-hidden
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-subtle bg-bg-subtle font-mono text-[10px] font-semibold tracking-wider"
                >
                  {item.short}
                </span>
                <span className="truncate">{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </Sheet>

      <nav
        data-testid="mobile-bottom-nav"
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border-subtle bg-bg-panel/95 backdrop-blur sm:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        {BOTTOM_NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex min-h-touch flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium",
                isActive ? "text-accent" : "text-fg-muted",
              )
            }
          >
            <span
              aria-hidden
              className="inline-flex h-5 w-7 items-center justify-center rounded font-mono text-[10px] tracking-wider"
            >
              {item.short}
            </span>
            <span className="truncate px-1">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}
