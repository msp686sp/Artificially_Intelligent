import { useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { Topbar } from "./Topbar";
import { useMediaQuery } from "@/hooks/useMediaQuery";

interface ShellProps {
  children: ReactNode;
}

/**
 * Shell — full-page chrome: Sidebar (sm+) / MobileNav (<sm) + Topbar +
 * a scrollable main pane. All routes render inside this layout via
 * <Outlet> from App.tsx.
 *
 * Responsive behavior (plan §6):
 *   < sm  → sidebar hidden, mobile drawer + bottom nav surfaces
 *   sm–lg → collapsed icon-only sidebar
 *   ≥ lg  → full sidebar with labels
 */
export function Shell({ children }: ShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg text-fg">
      <Sidebar collapsed={!isDesktop} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setMobileOpen(true)} />
        <main
          id="main-content"
          className="flex-1 overflow-y-auto px-3 pb-20 pt-4 sm:px-6 sm:pb-6 sm:pt-6"
        >
          <div className="mx-auto w-full max-w-7xl">{children}</div>
        </main>
      </div>
      <MobileNav open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </div>
  );
}
