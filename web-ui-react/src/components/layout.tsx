import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge } from "./ui";
import { useState } from "react";
import type { PropsWithChildren } from "react";

const navItems = [
  { to: "/", label: "Dashboard", icon: "🏠" },
  { to: "/views", label: "Views", icon: "👁️" },
  { to: "/organizations", label: "Organizations", icon: "🏢" },
  { to: "/logs", label: "Pipeline Console", icon: "📜" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
];

export function AppLayout({ children }: PropsWithChildren) {
  const [mappingMenuCollapsed, setMappingMenuCollapsed] = useState(false);
  const [emailMenuCollapsed, setEmailMenuCollapsed] = useState(false);
  const healthQ = useQuery({ queryKey: ["health-layout"], queryFn: api.health, retry: 0 });
  const pipelineStatusQ = useQuery({ queryKey: ["pipeline-status-layout"], queryFn: api.getPipelineStatus, refetchInterval: 5000 });
  const settingsConfigQ = useQuery({ queryKey: ["ui-pref", "settings-config"], queryFn: () => api.getUiPreference("settings-config"), staleTime: 60_000 });
  const googleOAuthUrl = (() => {
    const direct = (import.meta.env.VITE_GOOGLE_OAUTH_URL as string | undefined)?.trim();
    if (direct) return direct;
    const fromConfig = settingsConfigQ.data?.value;
    const savedClientId =
      fromConfig && typeof fromConfig === "object" && typeof fromConfig.googleClientId === "string"
        ? fromConfig.googleClientId.trim()
        : "";
    const envClientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim() || "";
    const clientId = savedClientId || envClientId;
    if (!clientId) return "";
    const redirectUri =
      (import.meta.env.VITE_GOOGLE_REDIRECT_URI as string | undefined)?.trim() ||
      (typeof window !== "undefined" ? `${window.location.origin}/` : "http://localhost:5173/");
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "https://www.googleapis.com/auth/gmail.send",
      access_type: "offline",
      prompt: "consent",
    });
    return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  })();
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
          <button
            type="button"
            className="sidebar-panel-toggle"
            onClick={() => setMappingMenuCollapsed((v) => !v)}
            aria-expanded={!mappingMenuCollapsed}
            aria-label={mappingMenuCollapsed ? "Expand mapping menu" : "Collapse mapping menu"}
          >
            <span className="sidebar-title">Mapping</span>
            <span>{mappingMenuCollapsed ? "▸" : "▾"}</span>
          </button>
          {!mappingMenuCollapsed ? (
            <nav className="sidebar-nav">
              {navItems.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                  <span className="nav-item-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          ) : null}
        </div>
        <div className="sidebar-panel">
          <button
            type="button"
            className="sidebar-panel-toggle"
            onClick={() => setEmailMenuCollapsed((v) => !v)}
            aria-expanded={!emailMenuCollapsed}
            aria-label={emailMenuCollapsed ? "Expand email menu" : "Collapse email menu"}
          >
            <span className="sidebar-title">Email</span>
            <span>{emailMenuCollapsed ? "▸" : "▾"}</span>
          </button>
          {!emailMenuCollapsed ? (
            <nav className="sidebar-nav">
              {navItems.map((item) => (
                <NavLink key={`email-${item.to}`} to={item.to} end={item.to === "/"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
                  <span className="nav-item-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          ) : null}
        </div>

        <div className="sidebar-status-card">
          <div className="sidebar-title">Pipeline Status</div>
          <div className="column gap-sm">
            {pipelineStatusQ.isPending ? (
              <Badge tone="warn">🟡 Checking...</Badge>
            ) : pipelineStatusQ.data?.running ? (
              <Badge tone="warn">🟠 RUNNING</Badge>
            ) : (
              <Badge tone="neutral">🟢 IDLE</Badge>
            )}
          </div>
        </div>

        <div className="sidebar-status-card">
          <div className="sidebar-title">System Status</div>
          <div className="column gap-sm">
            <Badge tone={healthQ.isSuccess ? "ok" : "warn"}>
              {healthQ.isPending ? "Checking API..." : healthQ.isSuccess ? "API Ready" : "API Offline"}
            </Badge>
            <Badge tone={googleOAuthUrl ? "ok" : "warn"}>
              {googleOAuthUrl ? "Gmail OAuth Ready" : "Gmail OAuth Not Configured"}
            </Badge>
            <span className="sidebar-status-note">Use Settings to verify API URL and backend service.</span>
          </div>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

