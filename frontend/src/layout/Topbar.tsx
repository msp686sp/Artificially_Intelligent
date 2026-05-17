import { useLocation } from "react-router-dom";
import { useTheme } from "@/hooks/useTheme";
import { NAV_ITEMS } from "./navConfig";
import { Button } from "@/components/Button";
import { Tooltip } from "@/components/Tooltip";

interface TopbarProps {
  onOpenMobileNav: () => void;
}

function lookupTitle(pathname: string): string {
  // Find the most-specific nav item that prefixes the current path.
  const match = NAV_ITEMS.slice()
    .sort((a, b) => b.path.length - a.path.length)
    .find((item) => (item.path === "/" ? pathname === "/" : pathname.startsWith(item.path)));
  return match?.label ?? "Rental";
}

/**
 * Topbar — the desktop/mobile header. Houses the page title (derived
 * from the active route), a theme toggle, and on mobile a hamburger
 * that opens the navigation sheet.
 */
export function Topbar({ onOpenMobileNav }: TopbarProps) {
  const location = useLocation();
  const { resolved, toggle } = useTheme();
  const title = lookupTitle(location.pathname);
  return (
    <header
      data-testid="topbar"
      className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border-subtle bg-bg-panel/95 px-3 backdrop-blur sm:px-4"
    >
      <button
        type="button"
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
        className="inline-flex min-h-touch min-w-touch items-center justify-center rounded-md text-fg-muted hover:bg-bg-subtle hover:text-fg sm:hidden"
      >
        <span aria-hidden className="flex flex-col items-center justify-center gap-1">
          <span className="h-0.5 w-5 rounded bg-current" />
          <span className="h-0.5 w-5 rounded bg-current" />
          <span className="h-0.5 w-5 rounded bg-current" />
        </span>
      </button>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold text-fg">{title}</h1>
        <div className="truncate text-[11px] text-fg-muted">{location.pathname}</div>
      </div>
      <Tooltip content={`Switch to ${resolved === "dark" ? "light" : "dark"} theme`}>
        <Button variant="ghost" size="sm" onClick={toggle} aria-label="Toggle theme">
          {resolved === "dark" ? "Light" : "Dark"}
        </Button>
      </Tooltip>
    </header>
  );
}
