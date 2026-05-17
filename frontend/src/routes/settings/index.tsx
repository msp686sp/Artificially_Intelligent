import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import {
  getMobileNavEnabled,
  setMobileNavEnabled,
  useTheme,
} from "@/layout/ThemeProvider";
import { useHealth, useVersion } from "@/hooks/useVersion";
import { useToast } from "@/components/Toast";

const THEMES: Array<{ value: "light" | "dark" | "auto"; label: string }> = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "auto", label: "Auto" },
];

export default function SettingsPage() {
  const { theme, setTheme, resolved } = useTheme();
  const version = useVersion();
  const health = useHealth();
  const toast = useToast();
  const [mobileNav, setMobileNav] = useState(true);

  useEffect(() => {
    setMobileNav(getMobileNavEnabled());
  }, []);

  const toggleMobileNav = (enabled: boolean) => {
    setMobileNav(enabled);
    setMobileNavEnabled(enabled);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("rental-gui:mobile-nav-changed"));
    }
    toast.success(`Mobile bottom-nav ${enabled ? "enabled" : "disabled"}.`);
  };

  return (
    <div className="stack" style={{ gap: "1.5rem" }}>
      <header className="row">
        <h1 style={{ margin: 0 }}>Settings</h1>
      </header>

      <Card title="Environment">
        <dl className="kv-list">
          <dt>RENTAL_WAREHOUSE_PATH</dt>
          <dd className="mono">
            {health.data?.warehouse_path ?? (
              <span className="muted">unset / not reported</span>
            )}
          </dd>
          <dt>RENTAL_MANIFEST_PATH</dt>
          <dd className="mono">
            {health.data?.manifest_path ?? (
              <span className="muted">unset / not reported</span>
            )}
          </dd>
          <dt>API status</dt>
          <dd>
            <Badge
              status={
                health.data?.status === "ok"
                  ? "ok"
                  : health.data?.status === "degraded"
                    ? "stale"
                    : "error"
              }
            >
              {health.data?.status ?? "unknown"}
            </Badge>
          </dd>
          {health.data?.uptime_s !== undefined && (
            <>
              <dt>Uptime</dt>
              <dd>{Math.floor(health.data.uptime_s / 60)} minutes</dd>
            </>
          )}
        </dl>
      </Card>

      <Card title="Version">
        {version.isLoading ? (
          <div className="muted">Loading…</div>
        ) : version.isError ? (
          <div className="muted">Version endpoint unavailable.</div>
        ) : version.data ? (
          <dl className="kv-list">
            <dt>API</dt>
            <dd className="mono">{version.data.api}</dd>
            <dt>App</dt>
            <dd className="mono">{version.data.app}</dd>
            <dt>Python</dt>
            <dd className="mono">{version.data.python}</dd>
          </dl>
        ) : null}
      </Card>

      <Card title="Appearance">
        <fieldset style={{ border: "none", padding: 0 }}>
          <legend className="muted" style={{ marginBottom: "0.5rem" }}>
            Theme (currently rendering: <strong>{resolved}</strong>)
          </legend>
          <div className="row" role="radiogroup" aria-label="Theme">
            {THEMES.map((t) => (
              <label
                key={t.value}
                className="row"
                style={{
                  gap: "0.25rem",
                  padding: "0.5rem 0.75rem",
                  border: "1px solid var(--border)",
                  borderRadius: "0.5rem",
                  cursor: "pointer",
                  minHeight: 44,
                }}
              >
                <input
                  type="radio"
                  name="theme"
                  value={t.value}
                  checked={theme === t.value}
                  onChange={() => setTheme(t.value)}
                  style={{ minHeight: 0 }}
                />
                {t.label}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset style={{ border: "none", padding: 0, marginTop: "1rem" }}>
          <legend className="muted" style={{ marginBottom: "0.5rem" }}>
            Mobile bottom-nav
          </legend>
          <label
            className="row"
            style={{
              gap: "0.5rem",
              padding: "0.5rem 0.75rem",
              border: "1px solid var(--border)",
              borderRadius: "0.5rem",
              cursor: "pointer",
              minHeight: 44,
              width: "fit-content",
            }}
          >
            <input
              type="checkbox"
              checked={mobileNav}
              onChange={(e) => toggleMobileNav(e.target.checked)}
              style={{ minHeight: 0 }}
            />
            Show bottom navigation on mobile
          </label>
        </fieldset>
      </Card>

      <Card title="About">
        <p className="muted" style={{ marginTop: 0 }}>
          Rental Market Analysis platform — local-first, single-user. The GUI
          is a window into the existing CLI workflows.
        </p>
        <ul style={{ paddingLeft: "1.25rem" }}>
          <li>
            <a
              href="/README.md"
              target="_blank"
              rel="noreferrer noopener"
            >
              README
            </a>
          </li>
          <li>
            <a
              href="/docs/plan.md"
              target="_blank"
              rel="noreferrer noopener"
            >
              docs/plan.md
            </a>
          </li>
          <li>
            <a
              href="/docs/gooey-plan.md"
              target="_blank"
              rel="noreferrer noopener"
            >
              docs/gooey-plan.md
            </a>
          </li>
        </ul>
      </Card>
    </div>
  );
}
