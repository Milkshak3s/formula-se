import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api/client";
import { Badge } from "./ui";
import type { Role } from "../api/types";

interface NavItem {
  to: string;
  label: string;
  role?: Role;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

// Two groups: the day-to-day "Play" tabs, and the admin/setup tabs. Setup pages
// stay visible to everyone (read-only for non-admins); only the Admin panel is
// role-gated. Empty sections (all items gated out) render nothing.
const NAV: NavSection[] = [
  {
    title: "Play",
    items: [
      { to: "/", label: "Dashboard" },
      { to: "/sector-map", label: "Sector Map" },
      { to: "/slots", label: "Blueprint Slots" },
      { to: "/start-world", label: "Start a World", role: "commander" },
      { to: "/prepared-worlds", label: "Prepared Worlds" },
    ],
  },
  {
    title: "Admin",
    items: [
      { to: "/ship-classes", label: "Ship Classes" },
      { to: "/maps", label: "Game Maps" },
      { to: "/station-types", label: "Station Types" },
      { to: "/admin", label: "Admin", role: "admin" },
    ],
  },
];

export function Layout({ children }: { children: ReactNode }) {
  const { user, hasRole, refresh } = useAuth();
  const navigate = useNavigate();

  const logout = async () => {
    await api.logout();
    refresh();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 border-r border-border bg-surface p-4 flex flex-col">
        <div className="px-2 py-3 mb-2">
          <div className="text-lg font-bold tracking-tight">Formula SE</div>
          <div className="text-xs text-muted">Space Engineers campaigns</div>
        </div>
        <nav className="flex-1 space-y-5">
          {NAV.map((section) => {
            const items = section.items.filter((n) => !n.role || hasRole(n.role));
            if (!items.length) return null;
            return (
              <div key={section.title ?? "main"} className="space-y-1">
                {section.title && (
                  <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted/70">
                    {section.title}
                  </div>
                )}
                {items.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.to === "/"}
                    className={({ isActive }) =>
                      `block rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                        isActive ? "bg-amber/20 text-amber-dark" : "text-ink hover:bg-cream"
                      }`
                    }
                  >
                    {n.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        {user && (
          <div className="border-t border-border pt-3 mt-3">
            <div className="px-2 mb-2">
              <div className="text-sm font-medium truncate">{user.display_name}</div>
              <div className="mt-1">
                <Badge tone="amber">{user.role}</Badge>
              </div>
            </div>
            <button className="btn-ghost w-full" onClick={logout}>
              Sign out
            </button>
          </div>
        )}
      </aside>
      <main className="flex-1 p-8 max-w-6xl">{children}</main>
    </div>
  );
}
