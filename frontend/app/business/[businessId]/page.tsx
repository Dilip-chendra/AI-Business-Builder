"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Activity, BarChart3, Bot, Boxes, ChevronRight, Globe, Megaphone, Rocket, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Business, MarketingCampaign, Product } from "@/lib/types";

type OperatingSummary = {
  counts?: Record<string, number>;
  recent_activity?: Array<{ id: string; type: string; label: string; detail: string; href: string; created_at?: string | null }>;
};

export default function BusinessWorkspacePage() {
  const params = useParams<{ businessId: string }>();
  const businessId = params.businessId;
  const [business, setBusiness] = useState<Business | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<MarketingCampaign[]>([]);
  const [summary, setSummary] = useState<OperatingSummary | null>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!businessId) return;
      setLoading(true);
      setError("");
      try {
        const [businesses, productRows, campaignRows, operatingSummary, reportRows] = await Promise.all([
          api.listBusinesses(),
          api.listProducts(businessId).catch(() => []),
          api.listCampaigns(businessId).catch(() => []),
          api.getOperatingSummary(businessId).catch(() => null),
          api.listAgentReports(businessId, 6).catch(() => []),
        ]);
        if (!mounted) return;
        setBusiness((businesses || []).find((item) => item.id === businessId) || null);
        setProducts(productRows as Product[]);
        setCampaigns(campaignRows as MarketingCampaign[]);
        setSummary(operatingSummary as OperatingSummary | null);
        setReports(reportRows as any[]);
      } catch (err: any) {
        if (mounted) setError(err?.message || "Could not load business workspace.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [businessId]);

  const actions = useMemo(() => [
    { href: `/landing/${businessId}`, label: "Preview Landing", icon: Globe, tone: "#06b6d4" },
    { href: `/ai-studio`, label: "Open AI Studio", icon: Sparkles, tone: "#8b5cf6" },
    { href: `/marketing?business_id=${businessId}`, label: "Marketing Engine", icon: Megaphone, tone: "#10b981" },
    { href: `/agent-live`, label: "Run Agents", icon: Bot, tone: "#f59e0b" },
  ], [businessId]);

  if (loading) {
    return <div style={{ padding: 32, color: "#64748b" }}>Loading business operating workspace...</div>;
  }

  if (error || !business) {
    return (
      <div style={{ padding: 32 }}>
        <div style={{ borderRadius: 20, background: "#fff", border: "1px solid #fee2e2", padding: 24, color: "#991b1b" }}>
          {error || "Business not found."}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      <section style={{ position: "relative", overflow: "hidden", borderRadius: 28, background: "linear-gradient(135deg,#070b1a,#111827 48%,#1e1b4b)", border: "1px solid rgba(129,140,248,0.25)", padding: "30px 32px", color: "#fff", boxShadow: "0 28px 90px rgba(15,23,42,0.18)" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 12% 5%,rgba(34,211,238,0.18),transparent 32%),radial-gradient(circle at 82% 8%,rgba(168,85,247,0.22),transparent 36%)" }} />
        <div style={{ position: "relative", display: "grid", gridTemplateColumns: "1fr auto", gap: 18, alignItems: "center" }}>
          <div>
            <p style={{ margin: "0 0 8px", color: "#a5b4fc", fontSize: 12, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase" }}>Business Operating Workspace</p>
            <h1 style={{ margin: 0, fontSize: "clamp(30px, 5vw, 56px)", lineHeight: 1.02, fontWeight: 950 }}>{business.name}</h1>
            <p style={{ margin: "14px 0 0", maxWidth: 760, color: "rgba(226,232,240,0.72)", fontSize: 15, lineHeight: 1.7 }}>{business.description || business.headline || "Your business modules, AI workflows, products, campaigns, reports, and analytics live here."}</p>
          </div>
          <div style={{ width: 96, height: 96, borderRadius: 28, background: "linear-gradient(135deg,#6366f1,#22d3ee)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 55px rgba(99,102,241,0.45)" }}>
            <Rocket size={42} />
          </div>
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 14 }}>
        {actions.map(({ href, label, icon: Icon, tone }) => (
          <Link key={href} href={href} className="card-lift" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, borderRadius: 18, border: "1px solid #e2e8f0", background: "#fff", padding: "18px 20px", textDecoration: "none", boxShadow: `0 16px 44px ${tone}12` }}>
            <span style={{ display: "flex", alignItems: "center", gap: 12, color: "#0f172a", fontWeight: 900 }}>
              <span style={{ width: 38, height: 38, borderRadius: 13, background: `${tone}18`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Icon size={18} color={tone} />
              </span>
              {label}
            </span>
            <ChevronRight size={16} color="#94a3b8" />
          </Link>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 16 }}>
        {[
          { label: "Products", value: products.length, icon: Boxes, tone: "#0ea5e9" },
          { label: "Campaigns", value: campaigns.length, icon: Megaphone, tone: "#10b981" },
          { label: "Agent Reports", value: reports.length, icon: Bot, tone: "#8b5cf6" },
          { label: "Analytics Events", value: summary?.counts?.analytics_events ?? 0, icon: BarChart3, tone: "#f59e0b" },
        ].map(({ label, value, icon: Icon, tone }) => (
          <div key={label} style={{ borderRadius: 20, border: "1px solid #e2e8f0", background: "#fff", padding: 20, boxShadow: "0 18px 50px rgba(15,23,42,0.06)" }}>
            <Icon size={20} color={tone} />
            <p style={{ margin: "18px 0 4px", fontSize: 34, fontWeight: 950, color: "#0f172a", lineHeight: 1 }}>{value}</p>
            <p style={{ margin: 0, color: "#64748b", fontSize: 13, fontWeight: 800 }}>{label}</p>
          </div>
        ))}
      </div>

      <section style={{ display: "grid", gridTemplateColumns: "minmax(0,1.1fr) minmax(280px,.9fr)", gap: 16 }}>
        <div style={{ borderRadius: 22, border: "1px solid #e2e8f0", background: "#fff", padding: 22 }}>
          <h2 style={{ margin: "0 0 14px", color: "#0f172a", fontSize: 20, fontWeight: 950 }}>Recent Activity</h2>
          <div className="abb-scroll-thin" style={{ display: "grid", gap: 10, maxHeight: 300, overflowY: "auto", paddingRight: 4 }}>
            {(summary?.recent_activity || []).length === 0 ? (
              <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>No persisted actions yet. Run AI Studio, Browser Agent, Marketing, or Code Editor to build this workspace.</p>
            ) : (
              summary!.recent_activity!.map((item) => (
                <Link key={`${item.type}-${item.id}`} href={item.href} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, alignItems: "center", textDecoration: "none", borderRadius: 14, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                  <span>
                    <strong style={{ display: "block", color: "#0f172a", fontSize: 13 }}>{item.label}</strong>
                    <span style={{ color: "#64748b", fontSize: 12 }}>{item.detail}</span>
                  </span>
                  <Activity size={15} color="#6366f1" />
                </Link>
              ))
            )}
          </div>
        </div>
        <div style={{ borderRadius: 22, border: "1px solid rgba(99,102,241,0.22)", background: "linear-gradient(145deg,#111827,#1e1b4b)", padding: 22, color: "#fff" }}>
          <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 950 }}>Business Context</h2>
          <p style={{ margin: "0 0 16px", color: "rgba(226,232,240,0.7)", fontSize: 13, lineHeight: 1.65 }}>{business.niche || "No niche set"} · {business.target_audience || "Audience pending"}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {[business.brand_tone, business.monetization_model, business.cta_text].filter(Boolean).map((item) => (
              <span key={String(item)} style={{ border: "1px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.07)", borderRadius: 999, padding: "7px 10px", color: "#dbeafe", fontSize: 12, fontWeight: 800 }}>{String(item)}</span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
