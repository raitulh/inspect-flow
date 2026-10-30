"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, AlertTriangle, Camera, ChevronDown, Factory, FileChartColumn, LayoutDashboard, LogOut, Menu, ScanEye, Settings2, ShieldCheck, SlidersHorizontal, X, PlugZap } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type User } from "@/lib/api";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/monitoring", label: "Video analysis", icon: Camera },
  { href: "/events", label: "Event review", icon: AlertTriangle },
  { href: "/stations", label: "Stations & rules", icon: Factory },
  { href: "/integrations", label: "Integrations", icon: PlugZap },
  { href: "/reports", label: "Reports", icon: FileChartColumn },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    if (path === "/login") return;
    let cancelled = false;
    api<User>("/api/v1/auth/me").then((current) => {
      if (!cancelled) setUser(current);
    }).catch(() => {
      if (!cancelled) router.replace("/login");
    });
    api<{ status: string }>("/healthz").then(() => !cancelled && setStatus("online")).catch(() => !cancelled && setStatus("offline"));
    return () => { cancelled = true; };
  }, [path, router]);

  async function logout() {
    try { await api("/api/v1/auth/logout", { method: "POST" }); } catch { /* The session may already have expired. */ }
    router.replace("/login");
  }

  if (path === "/login") return <>{children}</>;

  return (
    <div className="app-frame">
      {sidebarOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><ScanEye size={22} strokeWidth={1.8} /></div>
          <div><div className="brand-name">LineGuard<span>CV</span></div><div className="brand-sub">MANUFACTURING INTELLIGENCE</div></div>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><X size={18}/></button>
        </div>
        <div className="workspace-switcher">
          <div className="workspace-icon"><Factory size={18}/></div>
          <div className="workspace-copy"><strong>Plant operations</strong><span>Primary workspace</span></div>
          <ChevronDown size={15} className="muted-icon"/>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.href === "/" ? path === "/" : path === item.href || path.startsWith(`${item.href}/`);
            return <Link key={item.href} href={item.href} className={`nav-item ${active ? "active" : ""}`} onClick={() => setSidebarOpen(false)}><Icon size={18}/><span>{item.label}</span>{item.href === "/events" && <span className="nav-pin"/>}</Link>;
          })}
        </nav>
        <div className="nav-label nav-label-spaced">CONFIGURATION</div>
        <nav className="primary-nav" aria-label="Configuration navigation">
          <Link href="/stations" className={`nav-item ${path === "/stations" ? "active" : ""}`} onClick={() => setSidebarOpen(false)}><SlidersHorizontal size={18}/><span>Inspection rules</span></Link>
          <Link href="/integrations" className={`nav-item ${path.startsWith("/integrations") ? "active" : ""}`} onClick={() => setSidebarOpen(false)}><PlugZap size={18}/><span>Camera & PLC</span></Link><Link href="/reports" className={`nav-item ${path === "/reports" ? "active" : ""}`} onClick={() => setSidebarOpen(false)}><Settings2 size={18}/><span>System & reports</span></Link>
        </nav>
        <div className="sidebar-spacer"/>
        <div className="sidebar-health">
          <div className={`health-dot ${status === "online" ? "healthy" : status === "offline" ? "failed" : ""}`}/>
          <div className="health-copy"><strong>{status === "online" ? "API connected" : status === "offline" ? "API unavailable" : "Checking services"}</strong><span>{status === "online" ? "Local monitoring service" : status === "offline" ? "Check backend status" : "Connecting to API"}</span></div>
          <Activity size={16} className="muted-icon"/>
        </div>
        <div className="sidebar-user">
          <div className="avatar">{user?.email?.slice(0, 1).toUpperCase() || "L"}</div>
          <div className="user-copy"><strong>{user?.email || "LineGuard operator"}</strong><span>{user?.role || "Session loading"}</span></div>
          <button className="icon-button logout-button" onClick={logout} aria-label="Log out" title="Log out"><LogOut size={17}/></button>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20}/></button>
          <div className="topbar-breadcrumb"><span>Operations</span><span className="crumb-separator">/</span><strong>{navItems.find((item) => item.href === path)?.label || (path === "/" ? "Overview" : path.split("/").filter(Boolean).map((x) => x.charAt(0).toUpperCase() + x.slice(1)).join(" / "))}</strong></div>
          <div className="topbar-right"><span className={`status-pill ${status === "online" ? "status-online" : status === "offline" ? "status-offline" : ""}`}><span className="status-dot"/>{status === "online" ? "System online" : status === "offline" ? "Service offline" : "Checking"}</span><div className="topbar-divider"/><div className="user-mini"><div className="avatar avatar-small">{user?.email?.slice(0, 1).toUpperCase() || "L"}</div><span>{user?.email?.split("@")[0] || "Operator"}</span></div></div>
        </header>
        <div className="page-body">{children}</div>
        <footer className="app-footer"><span><ShieldCheck size={13}/> Evidence-first monitoring</span><span>LineGuard CV <b>v0.2.0</b></span></footer>
      </main>
    </div>
  );
}
