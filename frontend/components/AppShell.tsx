"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3, Boxes, LayoutDashboard,
  Menu, MessageCircle, Settings, Sparkles, X, LogOut,
  Loader2, Home, TrendingUp,
  Activity, Terminal, Shield, CreditCard,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { BusinessProjectSwitcher } from "@/components/BusinessProjectSwitcher";
import { api } from "@/lib/api";

// ── Nav structure ────────────────────────────────────────────

type NavItem = {
  href: string;
  label: string;
  icon: React.ElementType;
};

type NavGroup = {
  key: string;
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    key: "business",
    label: "Business Tools",
    items: [
      { href: "/dashboard",   label: "Dashboard",        icon: LayoutDashboard },
      { href: "/ai-studio",   label: "AI Studio",        icon: Sparkles },
      { href: "/marketing",   label: "Marketing Engine", icon: TrendingUp },
      { href: "/products",    label: "Products",         icon: Boxes },
      { href: "/analytics",   label: "Analytics",        icon: BarChart3 },
      { href: "/support",     label: "Support",          icon: MessageCircle },
    ],
  },
  {
    key: "developer",
    label: "Developer Tools",
    items: [
      { href: "/code-editor", label: "AI Code Editor",  icon: Terminal },
      { href: "/agent-live",  label: "Agent Live",       icon: Activity },
      { href: "/ops",         label: "AI Ops",           icon: Shield },
    ],
  },
  {
    key: "system",
    label: "System",
    items: [
      { href: "/settings",    label: "Settings",         icon: Settings },
      { href: "/billing",     label: "Billing",          icon: CreditCard },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, isLoading, logout } = useAuth();
  const [planLabel, setPlanLabel] = useState("Free");
  const isWorkspacePage =
    pathname.startsWith("/marketing") ||
    pathname.startsWith("/ai-studio") ||
    pathname.startsWith("/code-editor") ||
    pathname.startsWith("/agent-live");

  useEffect(() => {
    if (!user) return;
    api.getSubscription()
      .then((subscription) => setPlanLabel(subscription.plan.name))
      .catch(() => setPlanLabel("Free"));
  }, [user?.id]);

  const isPublicPage = pathname === "/" || pathname === "/login" || pathname === "/signup" || pathname.startsWith("/landing");
  /* ── Public pages: minimal top nav ─────────────────── */
  if (isPublicPage) {
    return (
      <div className="min-h-screen bg-white">
        <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-slate-100">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3.5">
            <Link href="/" className="flex items-center gap-3 group">
              <div
                className="h-9 w-9 rounded-xl flex items-center justify-center text-white text-sm font-black shadow-lg"
                style={{ background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)" }}
              >
                AB
              </div>
              <span className="hidden sm:block font-bold text-slate-800 text-base tracking-tight">
                Autonomous Business Builder
              </span>
              <span className="sm:hidden font-bold text-slate-800">ABB</span>
            </Link>
            <div className="flex items-center gap-2">
              {isLoading ? (
                <div className="h-8 w-20 rounded-lg bg-slate-100 animate-pulse" />
              ) : user ? (
                <Link
                  href="/dashboard"
                  className="flex items-center gap-2 text-sm font-semibold text-white px-4 py-2 rounded-xl btn-glow"
                  style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                >
                  <LayoutDashboard size={15} />
                  Dashboard
                </Link>
              ) : (
                <>
                  <Link href="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900 px-4 py-2 rounded-xl hover:bg-slate-50 transition">
                    Log in
                  </Link>
                  <Link
                    href="/signup"
                    className="text-sm font-semibold text-white px-5 py-2 rounded-xl btn-glow transition"
                    style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                  >
                    Get Started Free
                  </Link>
                </>
              )}
            </div>
          </div>
        </header>
        <main>{children}</main>
      </div>
    );
  }

  /* ── Private pages: sidebar layout ─────────────────── */
  const userInitial = (user?.full_name || user?.email || "U")[0].toUpperCase();
  const userName = user?.full_name || user?.email?.split("@")[0] || "User";

  return (
    <div className="abb-layout">

      {/* ── Sidebar ──────────────────────────────────── */}
      <aside className={`abb-sidebar${mobileOpen ? " is-open" : ""}`}>

        {/* Logo area */}
        <div style={{ padding: "20px 16px 16px", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
          <Link
            href="/dashboard"
            onClick={() => setMobileOpen(false)}
            style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontWeight: 800, fontSize: 13,
              boxShadow: "0 4px 16px rgba(99,102,241,0.5)", flexShrink: 0,
            }}>
              AB
            </div>
            <div>
              <div style={{ color: "#fff", fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>AI Business</div>
              <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 11, lineHeight: 1.2 }}>Builder</div>
            </div>
          </Link>
        </div>

        {/* Workspace Switcher */}
        <WorkspaceSwitcher />
        <BusinessProjectSwitcher />

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: "auto", padding: "8px 10px" }}>
          <Link
            href="/"
            onClick={() => setMobileOpen(false)}
            className="nav-item"
            style={{ marginBottom: 4 }}
          >
            <Home size={17} className="nav-icon" style={{ flexShrink: 0 }} />
            <span>Home</span>
          </Link>

          {NAV_GROUPS.map((group) => (
            <div key={group.key}>
              <div className="sidebar-section-label">{group.label}</div>
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={`nav-item${active ? " active" : ""}`}
                  >
                    <Icon size={17} className="nav-icon" style={{ flexShrink: 0 }} />
                    <span>{item.label}</span>
                    {active && (
                      <div style={{ marginLeft: "auto", width: 6, height: 6, borderRadius: "50%", background: "#818cf8" }} />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.07)", padding: "12px 10px" }}>
          {isLoading ? (
            <div style={{ height: 44, borderRadius: 10, background: "rgba(255,255,255,0.05)" }} />
          ) : user ? (
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 10px", borderRadius: 10, background: "rgba(255,255,255,0.05)",
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#fff", fontWeight: 700, fontSize: 13,
              }}>
                {userInitial}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ color: "#fff", fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {userName}
                  </div>
                  <span style={{ fontSize: 9, fontWeight: 700, background: "rgba(99,102,241,0.3)", color: "#a5b4fc", padding: "1px 5px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.05em", flexShrink: 0 }}>
                    {planLabel}
                  </span>
                </div>
                <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {user.email}
                </div>
              </div>
              <button
                onClick={logout}
                title="Log out"
                aria-label="Log out"
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: "rgba(255,255,255,0.4)", padding: 4, borderRadius: 6,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "color 0.15s", flexShrink: 0,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.9)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.4)")}
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────── */}
      <div className="abb-main">
        <header
          className="lg:hidden sticky top-0 z-50 flex items-center justify-between px-4 py-3"
          style={{
            background: isWorkspacePage ? "#0f172a" : "#fff",
            borderBottom: isWorkspacePage ? "none" : "1px solid #e2e8f0",
          }}
        >
          <Link href="/dashboard" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontWeight: 800, fontSize: 12,
            }}>
              AB
            </div>
            <span style={{ fontWeight: 700, color: isWorkspacePage ? "#f8fafc" : "#0f172a", fontSize: 15 }}>AI Business Builder</span>
          </Link>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            style={{
              padding: "6px 8px", borderRadius: 8, border: "1px solid #e2e8f0",
              background: isWorkspacePage ? "rgba(255,255,255,0.04)" : "#fff", cursor: "pointer", color: isWorkspacePage ? "#cbd5e1" : "#64748b",
              display: "flex", alignItems: "center",
            }}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </header>

        {isLoading ? (
          <div className="flex items-center justify-center" style={{ minHeight: "60vh" }}>
            <Loader2 className="animate-spin" size={32} style={{ color: "#cbd5e1" }} />
          </div>
        ) : (
          <main
            style={{
              flex: 1,
              padding: isWorkspacePage ? 0 : "24px 24px 40px",
              maxWidth: "100%",
              width: "100%",
              margin: 0,
              minWidth: 0,
              minHeight: isWorkspacePage ? "100vh" : undefined,
              background: isWorkspacePage ? "#0f172a" : "#f8fafc",
              boxSizing: "border-box",
            }}
          >
            {children}
          </main>
        )}
      </div>

      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)" }}
          onClick={() => setMobileOpen(false)}
        />
      )}
    </div>
  );
}
