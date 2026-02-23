import { NavLink } from "react-router-dom";
import { api } from "../lib/api";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "./ui";
import type { PropsWithChildren } from "react";

const navItems = [
  { to: "/", label: "Dashboard", icon: "🏠" },
  { to: "/views", label: "Views", icon: "👁️" },
  { to: "/customers", label: "Customers", icon: "👥" },
  { to: "/customer-details", label: "Customer Details", icon: "🧾" },
  { to: "/organizations", label: "Organizations", icon: "🏢" },
  { to: "/logs", label: "Logs", icon: "📜" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
];

export function AppLayout({ children }: PropsWithChildren) {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: 0 });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand-card">
          <div className="sidebar-brand-mark">MP</div>
          <div className="sidebar-brand">
            <strong>Mapping Pipeline</strong>
            <span>React Console</span>
          </div>
        </div>

        <div className="sidebar-panel">
          <div className="sidebar-title">Main Menu</div>
          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                <span className="nav-item-icon">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-status-card">
          <div className="sidebar-title">System Status</div>
          <div className="column gap-sm">
            <Badge tone={health.isSuccess ? "ok" : "warn"}>
              {health.isPending ? "Checking API..." : health.isSuccess ? "API Ready" : "API Offline"}
            </Badge>
            <span className="sidebar-status-note">Use Settings to verify API URL and backend service.</span>
          </div>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

