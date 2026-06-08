"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Sparkles, TrendingUp, Boxes, BarChart3, ArrowRight,
  Building2, Globe, Zap, Plus, ChevronRight, Bot,
  MessageCircle, Loader2, CreditCard, FolderKanban, BriefcaseBusiness,
} from "lucide-react";
import { useBusinesses } from "@/hooks/useData";
import { useAuth } from "@/lib/auth-context";
import { useActiveContext } from "@/lib/active-context";
import { api } from "@/lib/api";
import type { SubscriptionSummary } from "@/lib/types";

import dynamic from "next/dynamic";

const OnboardingChecklist = dynamic(
  () => import("@/components/OnboardingChecklist").then((mod) => mod.OnboardingChecklist),
  { ssr: false }
);

/* ── Quick action cards ─────────────────────────────── */
const ACTIONS = [
  {
    href: "/generator",
    icon: Sparkles,
    label: "Generate Business",
    desc: "AI builds your idea in 60s",
    gradient: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
    glow: "rgba(99,102,241,0.3)",
  },
  {
    href: "/products",
    icon: Boxes,
    label: "Add Products",
    desc: "Create & price your offerings",
    gradient: "linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%)",
    glow: "rgba(14,165,233,0.3)",
  },
  {
    href: "/marketing",
    icon: TrendingUp,
    label: "Launch Campaign",
    desc: "SEO, email & social ads",
    gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
    glow: "rgba(16,185,129,0.3)",
  },
  {
    href: "/analytics",
    icon: BarChart3,
    label: "View Analytics",
    desc: "Track conversions & revenue",
    gradient: "linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)",
    glow: "rgba(245,158,11,0.3)",
  },
];

/* ── Stat pill ──────────────────────────────────────── */
function StatPill({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold"
      style={{ background: color + "18", color }}
    >
      <span>{value}</span>
      <span style={{ opacity: 0.7 }}>{label}</span>
    </div>
  );
}

type OperatingSummary = {
  counts: {
    products: number;
    campaigns: number;
    agent_reports: number;
    studio_actions: number;
    code_versions: number;
    analytics_events: number;
  };
  recent_activity: Array<{
    id: string;
    type: string;
    label: string;
    detail: string;
    href: string;
    created_at?: string | null;
  }>;
};

type ProductIntelligence = {
  positioning?: {
    headline?: string;
    wedge?: string;
    why_now?: string;
  };
  market_opportunities?: Array<{ title: string; detail: string; priority: string }>;
  roadmap?: Array<{ phase: string; theme: string; tasks: string[] }>;
};

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const { data: businesses = [], isLoading: loading } = useBusinesses();
  const { activeWorkspace, activeBusiness, activeProject, isLoading: contextLoading } = useActiveContext();
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [operatingSummary, setOperatingSummary] = useState<OperatingSummary | null>(null);
  const [productIntelligence, setProductIntelligence] = useState<ProductIntelligence | null>(null);
  const [operatingLoading, setOperatingLoading] = useState(false);
  const createdBusinessId = searchParams.get("created_business");

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const name = user?.full_name || user?.email?.split("@")[0] || "there";

  useEffect(() => {
    api.getSubscription().then(setSubscription).catch(() => setSubscription(null));
    api.getProductIntelligence().then(setProductIntelligence).catch(() => setProductIntelligence(null));
  }, []);

  useEffect(() => {
    if (!activeBusiness?.id) {
      setOperatingSummary(null);
      return;
    }
    setOperatingLoading(true);
    api.getOperatingSummary(activeBusiness.id)
      .then(setOperatingSummary)
      .catch(() => setOperatingSummary(null))
      .finally(() => setOperatingLoading(false));
  }, [activeBusiness?.id]);

  return (
    <div className="anim-fade-in" style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* Onboarding checklist — shown until complete */}
      <OnboardingChecklist />

      {/* ── Hero greeting ─────────────────────────────── */}
      <div
        style={{
          borderRadius: 20,
          background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #0f172a 100%)",
          padding: "32px 36px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Decorative orbs */}
        <div style={{
          position: "absolute", top: -40, right: -40, width: 200, height: 200,
          borderRadius: "50%", background: "rgba(99,102,241,0.15)", filter: "blur(40px)",
        }} />
        <div style={{
          position: "absolute", bottom: -30, left: 100, width: 150, height: 150,
          borderRadius: "50%", background: "rgba(139,92,246,0.1)", filter: "blur(30px)",
        }} />

        <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 13, marginBottom: 6 }}>
              {greeting}
            </p>
            <h1 style={{ color: "#fff", fontSize: 26, fontWeight: 800, margin: 0, lineHeight: 1.2 }}>
              {name}
            </h1>
            <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 14, marginTop: 6 }}>
              {businesses.length === 0
                ? "Ready to build your first AI-powered business?"
                : `You have ${businesses.length} business${businesses.length > 1 ? "es" : ""} running.`}
            </p>
          </div>
          <Link
            href="/generator"
            className="btn-glow"
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              color: "#fff", fontWeight: 700, fontSize: 14,
              padding: "12px 22px", borderRadius: 12, textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            <Zap size={16} />
            New Business
          </Link>
        </div>
      </div>

      {createdBusinessId && activeBusiness && activeBusiness.id === createdBusinessId && (
        <div style={{ background: "linear-gradient(135deg,#eef2ff,#f5f3ff)", border: "1px solid #c7d2fe", borderRadius: 18, padding: "18px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Business Ready
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
              {activeBusiness.name} is now your active operating context.
            </div>
            <div style={{ fontSize: 13, color: "#64748b" }}>
              Next best move: preview the landing page, add a product, or launch a campaign tied to this business.
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Link href={`/landing/${activeBusiness.id}`} style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 16px", borderRadius: 12, background: "#fff", border: "1px solid #cbd5e1", color: "#334155", fontWeight: 700 }}>
              <Globe size={15} />
              Preview Landing
            </Link>
            <Link href="/products" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 16px", borderRadius: 12, background: "#fff", border: "1px solid #cbd5e1", color: "#334155", fontWeight: 700 }}>
              <Boxes size={15} />
              Add Products
            </Link>
            <Link href={`/marketing?business_id=${activeBusiness.id}`} style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 16px", borderRadius: 12, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700 }}>
              <TrendingUp size={15} />
              Open Marketing
            </Link>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1.2fr) minmax(280px, 1fr)", gap: 16 }}>
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: "0 0 12px" }}>
            Active Context
          </p>
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Building2 size={16} color="#6366f1" />
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700 }}>Workspace</div>
                <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>{activeWorkspace?.name || (contextLoading ? "Loading workspace..." : "Not selected")}</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: "#ecfeff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <BriefcaseBusiness size={16} color="#0891b2" />
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700 }}>Business</div>
                <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>{activeBusiness?.name || (contextLoading ? "Loading business..." : "Create or select a business")}</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: "#f5f3ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <FolderKanban size={16} color="#7c3aed" />
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700 }}>Project</div>
                <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>{activeProject?.name || (contextLoading ? "Loading project..." : "Starter project ready")}</div>
              </div>
            </div>
          </div>
        </div>

        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: 0 }}>
              Plan and Usage
            </p>
            <Link href="/billing" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6, color: "#6366f1", fontWeight: 700, fontSize: 12 }}>
              <CreditCard size={13} />
              Open Billing
            </Link>
          </div>
          {subscription ? (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>{subscription.plan.name}</div>
                <div style={{ fontSize: 12, color: "#64748b", textTransform: "capitalize" }}>{subscription.status.replaceAll("_", " ")}</div>
              </div>
              <div style={{ display: "grid", gap: 10 }}>
                {subscription.usage.slice(0, 3).map((item) => {
                  const ratio = item.unlimited || item.limit === null ? 18 : Math.min((item.used / Math.max(item.limit, 1)) * 100, 100);
                  return (
                    <div key={item.feature_key} style={{ display: "grid", gap: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 12 }}>
                        <span style={{ color: "#475569", textTransform: "capitalize" }}>{item.feature_key.replaceAll("_", " ")}</span>
                        <span style={{ color: "#0f172a", fontWeight: 700 }}>
                          {item.used}{item.unlimited ? " / Unlimited" : ` / ${item.limit}`}
                        </span>
                      </div>
                      <div style={{ height: 8, borderRadius: 999, background: "#eef2f7", overflow: "hidden" }}>
                        <div
                          style={{
                            width: `${ratio}%`,
                            height: "100%",
                            borderRadius: 999,
                            background: ratio > 85 ? "linear-gradient(135deg,#f59e0b,#ef4444)" : "linear-gradient(135deg,#6366f1,#8b5cf6)",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
              Billing data will appear here once your plan and usage have loaded.
            </p>
          )}
        </div>
      </div>

      {productIntelligence?.positioning && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(280px, 0.9fr) minmax(320px, 1.1fr)", gap: 16 }}>
          <div style={{ borderRadius: 22, padding: 22, color: "#e0f2fe", background: "linear-gradient(135deg,#07111f,#0f172a 58%,#164e63)", border: "1px solid rgba(34,211,238,0.24)", boxShadow: "0 24px 80px rgba(15,23,42,0.14)" }}>
            <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.12em", color: "#67e8f9" }}>Report-backed operating focus</p>
            <h2 style={{ margin: 0, color: "#fff", fontSize: 22, lineHeight: 1.15, fontWeight: 950 }}>{productIntelligence.positioning.headline}</h2>
            <p style={{ margin: "14px 0 0", color: "#bae6fd", fontSize: 13, lineHeight: 1.7 }}>{productIntelligence.positioning.wedge}</p>
            <p style={{ margin: "12px 0 0", color: "rgba(224,242,254,0.72)", fontSize: 13, lineHeight: 1.7 }}>{productIntelligence.positioning.why_now}</p>
          </div>
          <div style={{ borderRadius: 22, padding: 20, background: "#fff", border: "1px solid #dbeafe", boxShadow: "0 24px 70px rgba(15,23,42,0.08)" }}>
            <p style={{ margin: "0 0 12px", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.1em", color: "#6366f1" }}>Highest priority opportunities</p>
            <div style={{ display: "grid", gap: 10 }}>
              {(productIntelligence.market_opportunities || []).slice(0, 3).map((item) => (
                <div key={item.title} style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 12, padding: 12, borderRadius: 15, background: "#f8fafc", border: "1px solid #e2e8f0" }}>
                  <span style={{ alignSelf: "start", borderRadius: 999, padding: "4px 8px", background: "#eef2ff", color: "#4f46e5", fontSize: 11, fontWeight: 900 }}>{item.priority}</span>
                  <div>
                    <p style={{ margin: 0, fontSize: 13, color: "#0f172a", fontWeight: 900 }}>{item.title}</p>
                    <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>{item.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeBusiness && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16, alignItems: "stretch" }}>
          <div style={{ height: 360, background: "linear-gradient(145deg,#0f172a,#111827 54%,#1e1b4b)", borderRadius: 22, border: "1px solid rgba(129,140,248,0.28)", padding: 20, boxShadow: "0 24px 80px rgba(15,23,42,0.16)", overflow: "hidden", position: "relative", color: "#e2e8f0" }}>
            <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 15% 10%,rgba(99,102,241,0.24),transparent 30%),radial-gradient(circle at 90% 20%,rgba(34,211,238,0.16),transparent 34%)", pointerEvents: "none" }} />
            <div style={{ position: "relative", height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.1em", textTransform: "uppercase", color: "#a5b4fc", margin: "0 0 4px" }}>
                  Operating System State
                </p>
                <h2 style={{ margin: 0, fontSize: 20, color: "#fff", fontWeight: 900 }}>{activeBusiness.name}</h2>
              </div>
              {operatingLoading && <Loader2 size={16} color="#6366f1" className="animate-spin" />}
            </div>
            <div className="abb-scroll-thin" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, overflowY: "auto", paddingRight: 4, minHeight: 0 }}>
              {[
                { label: "Products", value: operatingSummary?.counts.products ?? 0, color: "#0ea5e9", href: "/products" },
                { label: "Campaigns", value: operatingSummary?.counts.campaigns ?? 0, color: "#10b981", href: "/marketing" },
                { label: "Agent Reports", value: operatingSummary?.counts.agent_reports ?? 0, color: "#8b5cf6", href: "/agent-live" },
                { label: "Studio Actions", value: operatingSummary?.counts.studio_actions ?? 0, color: "#6366f1", href: "/ai-studio" },
                { label: "Code Versions", value: operatingSummary?.counts.code_versions ?? 0, color: "#f59e0b", href: "/code-editor" },
                { label: "Analytics Events", value: operatingSummary?.counts.analytics_events ?? 0, color: "#ef4444", href: "/analytics" },
              ].map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    gap: 10,
                    minHeight: 86,
                    padding: "13px 14px",
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.1)",
                    background: "rgba(255,255,255,0.055)",
                    boxShadow: `inset 0 1px 0 rgba(255,255,255,0.06), 0 12px 34px ${item.color}12`,
                    textDecoration: "none",
                  }}
                >
                  <span style={{ color: "rgba(226,232,240,0.68)", fontSize: 12, fontWeight: 800 }}>{item.label}</span>
                  <span style={{ color: item.color, fontSize: 28, fontWeight: 950, lineHeight: 1 }}>{item.value}</span>
                </Link>
              ))}
            </div>
            </div>
          </div>

          <div style={{ height: 360, background: "linear-gradient(145deg,#ffffff,#f8fafc)", borderRadius: 22, border: "1px solid #dbeafe", padding: 20, boxShadow: "0 24px 70px rgba(15,23,42,0.09)", overflow: "hidden", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6366f1", margin: "0 0 4px" }}>
                  Recent Live Activity
                </p>
                <h2 style={{ margin: 0, fontSize: 18, color: "#0f172a", fontWeight: 800 }}>Connected workflow history</h2>
              </div>
              <div style={{ width: 38, height: 38, borderRadius: 13, background: "linear-gradient(135deg,#eef2ff,#e0e7ff)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 12px 30px rgba(99,102,241,0.16)" }}>
                <MessageCircle size={18} color="#6366f1" />
              </div>
            </div>
            {!operatingSummary || operatingSummary.recent_activity.length === 0 ? (
              <p style={{ margin: 0, color: "#64748b", fontSize: 13, lineHeight: 1.7 }}>
                Run AI Studio, Marketing Engine, Browser Agent, or Code Editor actions and they will appear here as real persisted activity.
              </p>
            ) : (
              <div className="abb-scroll-thin" style={{ display: "grid", gap: 10, overflowY: "auto", paddingRight: 4, minHeight: 0 }}>
                {operatingSummary.recent_activity.map((activity) => (
                  <Link
                    key={`${activity.type}-${activity.id}`}
                    href={activity.href}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr auto",
                      gap: 12,
                      alignItems: "center",
                      padding: "12px 14px",
                      borderRadius: 14,
                      border: "1px solid #e0e7ff",
                      background: "linear-gradient(135deg,#ffffff,#f8fbff)",
                      textDecoration: "none",
                      boxShadow: "0 10px 26px rgba(15,23,42,0.04)",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <p style={{ margin: "0 0 4px", color: "#0f172a", fontSize: 13, fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {activity.label}
                      </p>
                      <p style={{ margin: 0, color: "#64748b", fontSize: 12, textTransform: "capitalize" }}>
                        {activity.detail}
                        {activity.created_at ? ` - ${new Date(activity.created_at).toLocaleString()}` : ""}
                      </p>
                    </div>
                    <ChevronRight size={14} color="#94a3b8" />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Quick actions ─────────────────────────────── */}
      <div>
        <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", marginBottom: 12 }}>
          Quick Actions
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
          {ACTIONS.map(({ href, icon: Icon, label, desc, gradient, glow }) => (
            <Link
              key={href}
              href={href}
              className="card-lift"
              style={{
                display: "flex", flexDirection: "column", gap: 12,
                background: "#fff", borderRadius: 16, padding: "18px 18px",
                textDecoration: "none", border: "1px solid #e2e8f0",
                position: "relative", overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: 42, height: 42, borderRadius: 12,
                  background: gradient,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: `0 6px 20px ${glow}`,
                }}
              >
                <Icon size={20} color="#fff" />
              </div>
              <div>
                <p style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", margin: 0 }}>{label}</p>
                <p style={{ fontSize: 12, color: "#94a3b8", margin: "3px 0 0" }}>{desc}</p>
              </div>
              <ChevronRight
                size={14}
                style={{ position: "absolute", top: 18, right: 16, color: "#cbd5e1" }}
              />
            </Link>
          ))}
        </div>
      </div>

      {/* ── Businesses ────────────────────────────────── */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: 0 }}>
            Your Businesses ({businesses.length})
          </p>
          {businesses.length > 0 && (
            <Link href="/generator" style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, fontWeight: 600, color: "#6366f1", textDecoration: "none" }}>
              Add new <ArrowRight size={13} />
            </Link>
          )}
        </div>

        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
            {[1,2,3].map(i => (
              <div key={i} style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px 22px" }}>
                <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
                  <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div className="skeleton-line" style={{ width: "60%", marginBottom: 6 }} />
                    <div className="skeleton-line" style={{ width: "35%", height: 10 }} />
                  </div>
                </div>
                <div className="skeleton-line" style={{ width: "100%", marginBottom: 6 }} />
                <div className="skeleton-line" style={{ width: "80%" }} />
              </div>
            ))}
          </div>
        ) : businesses.length === 0 ? (
          /* Empty state — social proof + clear CTA */
          <div
            style={{
              borderRadius: 20, border: "2px dashed #e2e8f0", background: "#fff",
              padding: "56px 32px", textAlign: "center",
            }}
          >
            <div
              style={{
                width: 64, height: 64, borderRadius: 18, margin: "0 auto 16px",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: "0 8px 30px rgba(99,102,241,0.35)",
              }}
            >
              <Sparkles size={28} color="#fff" />
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", margin: "0 0 8px" }}>
              Build your first business
            </h3>
            <p style={{ fontSize: 14, color: "#64748b", maxWidth: 380, margin: "0 auto 24px", lineHeight: 1.6 }}>
              Describe your idea and our AI generates a complete business — name, products, landing page, and marketing strategy — in under 60 seconds.
            </p>
            <Link
              href="/generator"
              className="btn-glow"
              style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: "#fff", fontWeight: 700, fontSize: 15,
                padding: "13px 28px", borderRadius: 12, textDecoration: "none",
              }}
            >
              <Zap size={18} />
              Generate my first business
            </Link>
            <p style={{ marginTop: 12, fontSize: 12, color: "#94a3b8" }}>
              Takes about 30 seconds | Powered by real AI | No credit card
            </p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
            {businesses.map((biz: any) => (
              <article
                key={biz.id}
                onClick={(event) => {
                  const target = event.target as HTMLElement;
                  if (target.closest("a")) return;
                  window.location.href = `/business/${biz.id}`;
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    window.location.href = `/business/${biz.id}`;
                  }
                }}
                role="button"
                tabIndex={0}
                className="card-lift"
                style={{
                  display: "block",
                  background: "linear-gradient(145deg,#ffffff,#f8fbff)", borderRadius: 20, border: "1px solid #dbeafe",
                  padding: "20px 22px", overflow: "hidden", textDecoration: "none", boxShadow: "0 18px 48px rgba(15,23,42,0.07)", cursor: "pointer",
                }}
              >
                {/* Header */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
                  <div
                    style={{
                      width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                      background: "linear-gradient(135deg, #ede9fe, #ddd6fe)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}
                  >
                    <Building2 size={20} style={{ color: "#7c3aed" }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{ fontWeight: 800, fontSize: 15, color: "#0f172a", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {biz.name}
                    </h3>
                    {biz.niche && (
                      <span
                        style={{
                          display: "inline-block", marginTop: 4,
                          background: "#f1f5f9", color: "#64748b",
                          fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 99,
                        }}
                      >
                        {biz.niche}
                      </span>
                    )}
                  </div>
                </div>

                {/* Description */}
                {biz.description && (
                  <p style={{ fontSize: 13, color: "#64748b", lineHeight: 1.6, margin: "0 0 14px", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {biz.description}
                  </p>
                )}

                {/* Tags */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                  {biz.target_audience && (
                    <span style={{ background: "#f0fdf4", color: "#16a34a", fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 99 }}>
                      Audience: {biz.target_audience}
                    </span>
                  )}
                  {biz.monetization_model && (
                    <span style={{ background: "#fef3c7", color: "#d97706", fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 99 }}>
                      Monetization: {biz.monetization_model}
                    </span>
                  )}
                  {biz.product_count !== undefined && (
                    <span style={{ background: "#eff6ff", color: "#3b82f6", fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 99 }}>
                      {biz.product_count} Product{biz.product_count !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 6, borderTop: "1px solid #f1f5f9", paddingTop: 14 }}>
                  {[
                    { href: `/landing/${biz.id}`, icon: Globe, label: "Landing" },
                    { href: `/analytics`, icon: BarChart3, label: "Analytics" },
                    { href: `/products`, icon: Boxes, label: "Products" },
                    { href: `/agent`, icon: Bot, label: "Agent" },
                  ].map(({ href, icon: Icon, label }) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={(event) => event.stopPropagation()}
                      style={{
                        display: "flex", alignItems: "center", gap: 4,
                        fontSize: 12, fontWeight: 600, color: "#64748b",
                        textDecoration: "none", padding: "5px 8px", borderRadius: 8,
                        background: "#f8fafc", border: "1px solid #e2e8f0",
                        transition: "all 0.15s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "#ede9fe";
                        e.currentTarget.style.color = "#6366f1";
                        e.currentTarget.style.borderColor = "#c4b5fd";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "#f8fafc";
                        e.currentTarget.style.color = "#64748b";
                        e.currentTarget.style.borderColor = "#e2e8f0";
                      }}
                    >
                      <Icon size={12} />
                      {label}
                    </Link>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
