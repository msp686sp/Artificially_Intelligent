import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "./navConfig";
import { cn } from "@/lib/cn";

interface SidebarProps {
  /** Collapsed = icons only. Used at sm–lg breakpoints. */
  collapsed?: boolean;
}

/**
 * Sidebar — desktop navigation. At ≥ lg it shows full labels; between
 * sm and lg the consumer can pass `collapsed` to render an icons-only
 * column. Below sm the sidebar is replaced by <MobileNav>.
 */
export function Sidebar({ collapsed = false }: SidebarProps) {
  return (
    <aside
      data-testid="sidebar"
      className={cn(
        "hidden h-full shrink-0 flex-col border-r border-border-subtle bg-bg-panel sm:flex",
        collapsed ? "w-18" : "w-60",
      )}
    >
      <div className={cn("flex items-center gap-2 border-b border-border-subtle px-4 py-3")}>
        <span className="inline-block h-7 w-7 rounded-md bg-accent text-center text-sm font-bold leading-7 text-white">
          R
        </span>
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-sm font-semibold">Rental</div>
            <div className="text-[10px] uppercase tracking-wider text-fg-muted">analysis</div>
          </div>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.end}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-touch items-center gap-3 rounded-md px-3 text-sm transition-colors",
                    collapsed && "justify-center px-0",
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-fg-muted hover:bg-bg-subtle hover:text-fg",
                  )
                }
              >
                <span
                  aria-hidden
                  className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border-subtle bg-bg-subtle font-mono text-[10px] font-semibold tracking-wider"
                >
                  {item.short}
                </span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {!collapsed && (
        <div className="border-t border-border-subtle p-3 text-[11px] leading-relaxed text-fg-subtle">
          Local-first. Single-user.
        </div>
      )}
    </aside>
  );
}
