import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Home" },
  { to: "/sources", label: "Sources" },
  { to: "/manifest", label: "Manifest" },
  { to: "/logs", label: "Logs" },
  { to: "/settings", label: "Settings" },
];

export function MobileNav() {
  return (
    <nav className="mobile-nav" aria-label="Mobile">
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
  );
}
