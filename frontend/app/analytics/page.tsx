"use client";

import { useState } from "react";
import {
  BarChart3, MousePointerClick, ShoppingCart, Sparkles,
  Users, TrendingUp, DollarSign, Loader2, RefreshCw,
  Eye, ArrowUpRight, Activity
} from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useActiveContext } from "@/lib/active-context";
import { api } from "@/lib/api";
import { useAnalytics, useAnalyticsDashboard } from "@/hooks/useData";

type Suggestion = {
  headline: string | null; cta_text: string | null;
  pricing_note: string | null; positioning_note: string | null;
};

const STATS = [
  { key: "visitors",    label: "Total Visitors",  icon: Users,            gradient: "linear-gradient(135deg,#6366f1,#8b5cf6)", glow: "rgba(99,102,241,0.25)" },
  { key: "clicks",      label: "Total Clicks",    icon: MousePointerClick, gradient: "linear-gradient(135deg,#0ea5e9,#06b6d4)", glow: "rgba(14,165,233,0.25)" },
  { key: "conversions", label: "Conversions",     icon: ShoppingCart,     gradient: "linear-gradient(135deg,#10b981,#059669)", glow: "rgba(16,185,129,0.25)" },
  { key: "revenue",     label: "Revenue (USD)",   icon: DollarSign,       gradient: "linear-gradient(135deg,#f59e0b,#ef4444)", glow: "rgba(245,158,11,0.25)" },
];

export default function AnalyticsPage() {
  const { businesses, active, setActiveContext } = useActiveContext();
  const businessId = active.business_id || "";
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [optimizing, setOptimizing] = useState(false);

  // SWR hooks — cached, instant on revisit
  const { data: summary, isLoading: loading, mutate: refreshSummary } = useAnalytics(businessId);
  const { data: dashboard, mutate: refreshDashboard } = useAnalyticsDashboard(businessId);

  async function optimize() {
    if (!businessId) return;
    setOptimizing(true);
    try { setSuggestion(await api.optimize(businessId)); }
    catch (e) { console.error(e); }
    finally { setOptimizing(false); }
  }

  const vals: Record<string, string | number> = {
    visitors: summary?.visitors ?? 0,
    clicks: summary?.clicks ?? 0,
    conversions: summary?.conversions ?? 0,
    revenue: `${((summary?.revenue_cents ?? 0) / 100).toFixed(2)}`,
  };

  const convRate = ((summary?.conversion_rate ?? 0) * 100).toFixed(1);
  const hasData = summary && (summary.visitors > 0 || summary.clicks > 0);

  const chartData = (summary?.product_performance ?? []).slice(0, 6).map((p: any, i: number) => ({
    label: `P${i + 1}`,
    value: p.events,
  }));
  const maxVal = Math.max(...chartData.map((d: any) => d.value), 1);

  return (
    <ErrorBoundary>
      <div className="anim-fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
              <BarChart3 size={24} style={{ color: "#6366f1" }} /> Analytics
            </h1>
            <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Real-time performance data for your businesses.</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <select
              value={businessId}
              onChange={(e) => setActiveContext({ business_id: e.target.value, project_id: null }).catch(console.error)}
              style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", padding: "8px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
            >
              {businesses.map((b: any) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <button
              onClick={() => { refreshSummary(); refreshDashboard(); }}
              disabled={!businessId || loading}
              style={{ display: "flex", alignItems: "center", gap: 6, borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", color: "#64748b", padding: "8px 12px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
            <button
              onClick={optimize}
              disabled={!businessId || optimizing}
              style={{ display: "flex", alignItems: "center", gap: 6, borderRadius: 10, border: "1.5px solid #c4b5fd", background: "#ede9fe", color: "#6366f1", padding: "8px 14px", fontSize: 13, fontWeight: 700, cursor: !businessId || optimizing ? "not-allowed" : "pointer", opacity: !businessId || optimizing ? 0.6 : 1, fontFamily: "inherit" }}
            >
              {optimizing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {optimizing ? "Analyzing..." : "AI Optimize"}
            </button>
          </div>
        </div>

        {/* No data state */}
        {!loading && !hasData && (
          <div style={{ background: "linear-gradient(135deg,#0f172a,#1e1b4b)", borderRadius: 20, padding: "32px 36px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <Activity size={20} color="#818cf8" />
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#fff", margin: 0 }}>No traffic data yet</h3>
              </div>
              <p style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", margin: "0 0 6px", lineHeight: 1.6 }}>
                Analytics populate from real landing-page visits, product actions, AI workflows, campaign generation, and publishing activity.
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, flexShrink: 0 }}>
              <a
                href="/marketing"
                style={{ display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 12, padding: "12px 20px", fontSize: 14, fontWeight: 700, fontFamily: "inherit", boxShadow: "0 4px 20px rgba(99,102,241,0.4)", textDecoration: "none", justifyContent: "center" }}
              >
                <Sparkles size={16} /> Generate Real Campaign
              </a>
              {businessId && (
                <a
                  href={`/landing/${businessId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 12, padding: "10px 16px", fontSize: 13, fontWeight: 600, textDecoration: "none", justifyContent: "center" }}
                >
                  <Eye size={14} /> View Landing Page <ArrowUpRight size={12} />
                </a>
              )}
            </div>
          </div>
        )}

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 14 }}>
          {STATS.map(({ key, label, icon: Icon, gradient, glow }) => (
            <div key={key} className="card-lift" style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px 22px" }}>
              {loading ? (
                <div style={{ height: 80, background: "linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%)", backgroundSize: "200% 100%", borderRadius: 10, animation: "shimmer 1.5s infinite" }} />
              ) : (
                <>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: gradient, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 6px 20px ${glow}`, marginBottom: 14 }}>
                    <Icon size={20} color="#fff" />
                  </div>
                  <p style={{ fontSize: 28, fontWeight: 900, color: "#0f172a", margin: "0 0 4px" }}>{vals[key]}</p>
                  <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>{label}</p>
                </>
              )}
            </div>
          ))}
        </div>

        {/* Dashboard metrics */}
        {dashboard && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14 }}>
              <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "18px" }}>
                <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>AI Requests</p>
                <p style={{ fontSize: 28, fontWeight: 900, margin: "6px 0 0", color: "#0f172a" }}>{dashboard.ai_requests}</p>
              </div>
              <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "18px" }}>
                <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>Campaigns Generated</p>
                <p style={{ fontSize: 28, fontWeight: 900, margin: "6px 0 0", color: "#0f172a" }}>{dashboard.campaigns_generated}</p>
              </div>
              <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "18px" }}>
                <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>Job Success Rate</p>
                <p style={{ fontSize: 28, fontWeight: 900, margin: "6px 0 0", color: "#0f172a" }}>{(dashboard.success_rate * 100).toFixed(1)}%</p>
              </div>
            </div>
            {dashboard.usage_over_time?.length > 0 && (
              <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "24px" }}>
                <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 16px" }}>Usage Over Time</h2>
                <div style={{ display: "grid", gap: 8 }}>
                  {dashboard.usage_over_time.map((p: any) => (
                    <div key={p.date} style={{ display: "grid", gridTemplateColumns: "120px 1fr 60px 60px", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "#64748b" }}>{p.date}</span>
                      <div style={{ width: "100%", background: "#e2e8f0", borderRadius: 99, height: 8, overflow: "hidden" }}>
                        <div style={{ width: `${Math.min(100, p.ai_requests * 5)}%`, height: "100%", background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
                      </div>
                      <span style={{ fontSize: 12, color: "#334155", textAlign: "right" }}>{p.ai_requests}</span>
                      <span style={{ fontSize: 12, color: "#16a34a", textAlign: "right" }}>{p.campaigns_generated}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Conversion rate banner */}
        {!loading && summary && hasData && (
          <div style={{ borderRadius: 20, background: "linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#0f172a 100%)", padding: "28px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", top: -30, right: -30, width: 160, height: 160, borderRadius: "50%", background: "rgba(99,102,241,0.15)", filter: "blur(30px)" }} />
            <div style={{ position: "relative" }}>
              <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 13, margin: "0 0 6px" }}>Conversion Rate</p>
              <p style={{ color: "#fff", fontSize: 40, fontWeight: 900, margin: "0 0 4px" }}>{convRate}%</p>
              <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 13, margin: 0 }}>
                {summary.conversions} conversions from {summary.visitors} visitors
              </p>
            </div>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
              <TrendingUp size={30} color="rgba(255,255,255,0.7)" />
            </div>
          </div>
        )}

        {/* Product engagement chart */}
        {!loading && chartData.length > 0 && chartData.some((d: any) => d.value > 0) && (
          <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "24px" }}>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 20px" }}>Product Engagement</h2>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-end", height: 120 }}>
              {chartData.map((d: any, i: number) => (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <div style={{ width: "100%", borderRadius: "6px 6px 0 0", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", height: `${Math.max((d.value / maxVal) * 100, 4)}px`, transition: "height 0.5s ease", boxShadow: "0 4px 12px rgba(99,102,241,0.3)" }} />
                  <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{d.label}</span>
                  <span style={{ fontSize: 11, color: "#374151", fontWeight: 700 }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI optimization suggestions */}
        {suggestion && (
          <div style={{ background: "#fff", borderRadius: 20, border: "1.5px solid #c4b5fd", padding: "24px", boxShadow: "0 4px 24px rgba(99,102,241,0.1)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Sparkles size={16} color="#fff" />
              </div>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>AI Optimization Suggestions</h2>
                <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Based on your current analytics data</p>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { label: "Suggested Headline", value: suggestion.headline, color: "#6366f1" },
                { label: "Suggested CTA", value: suggestion.cta_text, color: "#10b981" },
                { label: "Pricing Strategy", value: suggestion.pricing_note, color: "#f59e0b" },
                { label: "Positioning", value: suggestion.positioning_note, color: "#0ea5e9" },
              ].filter((s) => s.value).map(({ label, value, color }) => (
                <div key={label} style={{ background: "#f8fafc", borderRadius: 12, border: "1px solid #e2e8f0", padding: "14px 16px" }}>
                  <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: "0 0 6px" }}>{label}</p>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", margin: 0, lineHeight: 1.5 }}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        )}


      </div>

      <style>{`
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </ErrorBoundary>
  );
}
