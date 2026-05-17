import { useEffect, useState } from "react";
import type { PropsWithChildren } from "react";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { HealthPill } from "@/components/HealthPill";
import { getMobileNavEnabled } from "./ThemeProvider";

export function Shell({ children }: PropsWithChildren) {
  const [mobileNav, setMobileNav] = useState(true);
  useEffect(() => {
    setMobileNav(getMobileNavEnabled());
    const handler = () => setMobileNav(getMobileNavEnabled());
    window.addEventListener("storage", handler);
    window.addEventListener("rental-gui:mobile-nav-changed", handler);
    return () => {
      window.removeEventListener("storage", handler);
      window.removeEventListener("rental-gui:mobile-nav-changed", handler);
    };
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <strong style={{ fontSize: "0.95rem" }}>Rental Market Analysis</strong>
        <HealthPill />
      </header>
      <Sidebar />
      <main className="content" role="main">
        {children}
      </main>
      {mobileNav && <MobileNav />}
    </div>
  );
}
