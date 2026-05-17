import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/sources", label: "Sources" },
  { to: "/manifest", label: "Manifest" },
  { to: "/logs", label: "Refresh log" },
  { to: "/rankings", label: "Rankings" },
  { to: "/sql", label: "SQL" },
  { to: "/schema", label: "Schema" },
  { to: "/backtest", label: "Backtest" },
  { to: "/settings", label: "Settings" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div
        style={{ padding: "0.25rem 0.75rem 1rem", fontWeight: 600 }}
        aria-hidden
      >
        Rental Market
      </div>
      <nav aria-label="Primary">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === "/"}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
