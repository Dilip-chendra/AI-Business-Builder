"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Calendar,
  Copy,
  Download,
  ExternalLink,
  Loader2,
  Mail,
  Megaphone,
  RefreshCw,
  Share2,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { useActiveContext } from "@/lib/active-context";
import { api } from "@/lib/api";
import type { MarketingCampaign } from "@/lib/types";
import { cleanDisplayText, truncateClean } from "@/lib/text";
import { useToast } from "@/components/Toast";

function formatCampaignBody(campaign: MarketingCampaign) {
  const content = campaign.content || {};
  return cleanDisplayText(
    content.executive_summary ||
      content.recommended_angle ||
      content.subject ||
      content.preview_text ||
      content.headline ||
      content.post_text ||
      content.body ||
      content.plain_text_body ||
      content.content_markdown ||
      (Array.isArray(content.posts)
        ? content.posts
            .map((post: any) => post?.text || post?.caption || "")
            .filter(Boolean)
            .join("\n\n")
        : "") ||
      ""
  );
}

function campaignLabel(type: string) {
  const map: Record<string, string> = {
    email: "Email",
    social: "Social",
    linkedin: "LinkedIn",
    twitter: "Twitter / X",
    instagram: "Instagram",
    facebook: "Facebook",
    google_ads: "Google Ads",
    meta_ads: "Meta Ads",
    seo_blog: "SEO Blog",
    research_brief: "Research Brief",
  };
  return map[type] || type.replace(/_/g, " ");
}

function platformIcon(type: string) {
  if (type === "email") return <Mail size={16} />;
  if (type === "google_ads" || type === "meta_ads") return <Megaphone size={16} />;
  if (type === "research_brief") return <Sparkles size={16} />;
  return <Share2 size={16} />;
}

function statusTone(status: string) {
  const map: Record<string, { bg: string; color: string }> = {
    draft: { bg: "#e2e8f0", color: "#475569" },
    pending_approval: { bg: "#fef3c7", color: "#b45309" },
    approved: { bg: "#dcfce7", color: "#15803d" },
    published: { bg: "#dbeafe", color: "#1d4ed8" },
    running: { bg: "#dbeafe", color: "#2563eb" },
    scheduled: { bg: "#ede9fe", color: "#7c3aed" },
    failed: { bg: "#fee2e2", color: "#dc2626" },
  };
  return map[status] || { bg: "#e2e8f0", color: "#475569" };
}

function renderResearchBrief(campaign: MarketingCampaign) {
  const content = campaign.content || {};
  const chipGroups = [
    { label: "Keywords", items: content.keywords || [], bg: "#dbeafe", color: "#1d4ed8" },
    { label: "Pricing", items: content.pricing_signals || [], bg: "#fef3c7", color: "#b45309" },
    { label: "Entities", items: content.competitor_or_entity_signals || [], bg: "#ede9fe", color: "#6d28d9" },
    { label: "Features", items: content.feature_signals || [], bg: "#dcfce7", color: "#15803d" },
  ];
  const evidence = Array.isArray(content.evidence) ? content.evidence : [];
  const sources = Array.isArray(content.sources) ? content.sources : [];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 800, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.08em" }}>Recommended Angle</p>
        <p style={{ margin: 0, color: "#0f172a", fontSize: 15, lineHeight: 1.65, fontWeight: 700 }}>{cleanDisplayText(content.recommended_angle || content.goal || campaign.name)}</p>
      </div>
      {content.executive_summary && (
        <div style={{ whiteSpace: "pre-wrap", color: "#334155", fontSize: 14, lineHeight: 1.75 }}>
          {truncateClean(cleanDisplayText(content.executive_summary), 1200)}
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {chipGroups.map((group) => {
          const items = Array.isArray(group.items) ? group.items.filter(Boolean).slice(0, 10) : [];
          if (!items.length) return null;
          return (
            <div key={group.label}>
              <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>{group.label}</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                {items.map((item: string, index: number) => (
                  <span key={`${group.label}-${index}`} style={{ borderRadius: 999, background: group.bg, color: group.color, padding: "5px 9px", fontSize: 11, fontWeight: 800 }}>
                    {truncateClean(cleanDisplayText(String(item)), 42)}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {(content.confidence || content.structured_density) && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
          <div style={{ borderRadius: 14, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "11px 12px" }}>
            <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Confidence</p>
            <p style={{ margin: 0, color: "#0f172a", fontSize: 16, fontWeight: 900 }}>{Math.round(Number(content.confidence || 0) * 100)}%</p>
          </div>
          <div style={{ borderRadius: 14, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "11px 12px" }}>
            <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Evidence Density</p>
            <p style={{ margin: 0, color: "#0f172a", fontSize: 16, fontWeight: 900 }}>{Number(content.structured_density || 0).toFixed(1)}</p>
          </div>
        </div>
      )}
      {evidence.length > 0 && (
        <div>
          <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Evidence Cards</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {evidence.slice(0, 3).map((item: any, index: number) => (
              <div key={`${item.url || index}`} style={{ borderRadius: 14, border: "1px solid #e2e8f0", background: "#f8fafc", padding: "11px 12px" }}>
                <p style={{ margin: "0 0 4px", color: "#0f172a", fontSize: 13, fontWeight: 800 }}>{truncateClean(cleanDisplayText(item.title || item.url || "Evidence source"), 90)}</p>
                {item.summary && <p style={{ margin: "0 0 6px", color: "#64748b", fontSize: 12, lineHeight: 1.55 }}>{truncateClean(cleanDisplayText(item.summary), 180)}</p>}
                {item.url && <p style={{ margin: 0, color: "#6366f1", fontSize: 11, wordBreak: "break-all" }}>{item.url}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
      {sources.length > 0 && (
        <p style={{ margin: 0, color: "#64748b", fontSize: 12, lineHeight: 1.55 }}>
          {sources.length} source{sources.length === 1 ? "" : "s"} attached to this brief.
        </p>
      )}
    </div>
  );
}

export default function MarketingGeneratedContentPage() {
  const { active, businesses } = useActiveContext();
  const toast = useToast();
  const [campaigns, setCampaigns] = useState<MarketingCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  const businessId = active.business_id || businesses[0]?.id || "";
  const businessName = useMemo(
    () => businesses.find((item) => item.id === businessId)?.name || "Active business",
    [businesses, businessId]
  );
  const stats = useMemo(() => {
    const totals = {
      total: campaigns.length,
      approved: 0,
      published: 0,
      drafts: 0,
    };
    for (const campaign of campaigns) {
      const status = campaign.lifecycle_status || campaign.status;
      if (status === "approved") totals.approved += 1;
      else if (status === "published") totals.published += 1;
      else if (status === "draft" || status === "pending_approval") totals.drafts += 1;
    }
    return totals;
  }, [campaigns]);

  const loadCampaigns = async () => {
    if (!businessId) {
      setCampaigns([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const rows = await api.listCampaigns(businessId);
      setCampaigns(rows);
    } catch (error: any) {
      toast.error(error.message || "Could not load generated content.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCampaigns();
  }, [businessId]);

  const handleCopy = async (campaign: MarketingCampaign) => {
    const body = formatCampaignBody(campaign);
    await navigator.clipboard.writeText(body || campaign.name);
    setCopiedId(campaign.id);
    toast.success("Content copied to clipboard.");
    window.setTimeout(() => setCopiedId(null), 1600);
  };

  const handleDownload = (campaign: MarketingCampaign) => {
    const body = formatCampaignBody(campaign);
    const blob = new Blob([body || cleanDisplayText(campaign.content)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${campaign.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "campaign"}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const startEdit = (campaign: MarketingCampaign) => {
    setEditingId(campaign.id);
    setDraftText(formatCampaignBody(campaign) || cleanDisplayText(campaign.content || {}));
  };

  const campaignBusinessId = (campaign: MarketingCampaign) => String(campaign.business_id || businessId || "");

  const saveEdit = async (campaign: MarketingCampaign) => {
    const targetBusinessId = campaignBusinessId(campaign);
    if (!targetBusinessId || !draftText.trim()) return;
    setSavingId(campaign.id);
    try {
      const updated = await api.updateCampaign(targetBusinessId, campaign.id, { content_text: draftText });
      setCampaigns((rows) => rows.map((row) => (row.id === campaign.id ? updated : row)));
      setEditingId(null);
      setDraftText("");
      toast.success("Campaign content saved.");
    } catch (error: any) {
      toast.error(error.message || "Could not save campaign content.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <section
        style={{
          borderRadius: 28,
          padding: "28px 30px",
          background: "linear-gradient(135deg, #0f172a 0%, #111827 45%, #1f1b4d 100%)",
          color: "#fff",
          border: "1px solid rgba(148,163,184,0.14)",
          boxShadow: "0 30px 80px rgba(15,23,42,0.22)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Link href="/marketing" style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "rgba(255,255,255,0.75)", textDecoration: "none", fontSize: 13, fontWeight: 600 }}>
              <ArrowLeft size={14} />
              Back to Marketing Engine
            </Link>
            <div>
              <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", color: "rgba(255,255,255,0.55)", textTransform: "uppercase" }}>
                Generated Content
              </p>
              <h1 style={{ margin: 0, fontSize: 34, lineHeight: 1.05, letterSpacing: "-0.03em" }}>Campaign library for {businessName}</h1>
            </div>
            <p style={{ margin: 0, maxWidth: 760, color: "rgba(255,255,255,0.72)", lineHeight: 1.7, fontSize: 14 }}>
              Review every generated campaign in one calm place. Each card is built to hold the full preview, actions, status, and export options without cramped scrollbars or overlapping controls.
            </p>
          </div>
          <button
            onClick={loadCampaigns}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid rgba(255,255,255,0.16)",
              background: "rgba(255,255,255,0.06)",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </section>

      {!loading && campaigns.length > 0 && (
        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16 }}>
          {[
            { label: "Total Assets", value: stats.total, tone: "#6366f1", bg: "#eef2ff" },
            { label: "Approved", value: stats.approved, tone: "#16a34a", bg: "#dcfce7" },
            { label: "Published", value: stats.published, tone: "#2563eb", bg: "#dbeafe" },
            { label: "Needs Review", value: stats.drafts, tone: "#b45309", bg: "#fef3c7" },
          ].map((card) => (
            <div
              key={card.label}
              style={{
                borderRadius: 22,
                background: "#fff",
                border: "1px solid #e2e8f0",
                padding: "18px 20px",
                boxShadow: "0 16px 40px rgba(15,23,42,0.06)",
              }}
            >
              <p style={{ margin: "0 0 10px", fontSize: 11, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.09em" }}>
                {card.label}
              </p>
              <p style={{ margin: 0, fontSize: 30, fontWeight: 900, color: card.tone }}>{card.value}</p>
              <div style={{ marginTop: 14, height: 8, borderRadius: 999, background: card.bg }} />
            </div>
          ))}
        </section>
      )}

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "100px 0" }}>
          <Loader2 size={34} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
          <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        </div>
      ) : campaigns.length === 0 ? (
        <div style={{ borderRadius: 24, background: "#fff", border: "1px solid #e2e8f0", padding: 40, textAlign: "center", color: "#475569" }}>
          <Sparkles size={28} style={{ color: "#6366f1", margin: "0 auto 12px" }} />
          <h2 style={{ margin: "0 0 8px", fontSize: 22, color: "#0f172a" }}>No generated content yet</h2>
          <p style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.7 }}>
            Run the Marketing Engine to generate campaigns, then come back here to review, copy, export, and launch them cleanly.
          </p>
          <Link href="/marketing" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 14, textDecoration: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700 }}>
            Open Marketing Engine
            <ExternalLink size={14} />
          </Link>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 22 }}>
          {campaigns.map((campaign) => {
            const body = formatCampaignBody(campaign);
            const tone = statusTone(campaign.lifecycle_status || campaign.status);
            return (
              <article
                key={campaign.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 18,
                  borderRadius: 26,
                  padding: 22,
                  background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 20px 60px rgba(15,23,42,0.08)",
                  minHeight: 420,
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ display: "flex", gap: 14, minWidth: 0 }}>
                    <div style={{ width: 44, height: 44, borderRadius: 14, background: "#eef2ff", color: "#4f46e5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      {platformIcon(campaign.campaign_type)}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <p style={{ margin: "0 0 6px", fontSize: 12, fontWeight: 700, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                        {campaignLabel(campaign.campaign_type)}
                      </p>
                      <h2 style={{ margin: 0, fontSize: 20, lineHeight: 1.25, color: "#0f172a", letterSpacing: "-0.02em" }}>{campaign.name}</h2>
                    </div>
                  </div>
                  <span style={{ padding: "7px 10px", borderRadius: 999, background: tone.bg, color: tone.color, fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0 }}>
                    {(campaign.lifecycle_status || campaign.status).replace(/_/g, " ")}
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
                  <div style={{ borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                    <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Platform</p>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{campaignLabel(campaign.campaign_type)}</p>
                  </div>
                  <div style={{ borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                    <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Created</p>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{new Date(campaign.created_at).toLocaleDateString()}</p>
                  </div>
                  <div style={{ borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                    <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Status</p>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: tone.color }}>{(campaign.lifecycle_status || campaign.status).replace(/_/g, " ")}</p>
                  </div>
                </div>

                <div style={{ borderRadius: 20, background: "#fff", border: "1px solid #e2e8f0", padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                    <p style={{ margin: 0, fontSize: 12, fontWeight: 800, color: "#0f172a", letterSpacing: "0.08em", textTransform: "uppercase" }}>AI Generated Content</p>
                    {copiedId === campaign.id && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "#16a34a", fontSize: 12, fontWeight: 700 }}>
                        <CheckCircle2 size={14} />
                        Copied
                      </span>
                    )}
                  </div>
                  {editingId === campaign.id ? (
                    <textarea
                      value={draftText}
                      onChange={(event) => setDraftText(event.target.value)}
                      rows={10}
                      style={{
                        width: "100%",
                        resize: "vertical",
                        border: "1px solid #cbd5e1",
                        borderRadius: 14,
                        padding: "12px 14px",
                        color: "#0f172a",
                        background: "#f8fafc",
                        fontSize: 14,
                        lineHeight: 1.7,
                        fontFamily: "inherit",
                        outline: "none",
                      }}
                    />
                  ) : (
                    campaign.campaign_type === "research_brief" ? (
                      renderResearchBrief(campaign)
                    ) : (
                      <div style={{ whiteSpace: "pre-wrap", color: "#334155", fontSize: 14, lineHeight: 1.8 }}>
                        {body || truncateClean(cleanDisplayText(campaign.content), 1200)}
                      </div>
                    )
                  )}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: "auto" }}>
                  <button onClick={() => handleCopy(campaign)} style={actionButton("#eef2ff", "#4338ca")}>
                    <Copy size={14} />
                    Copy
                  </button>
                  {editingId === campaign.id ? (
                    <>
                      <button onClick={() => saveEdit(campaign)} disabled={savingId === campaign.id} style={actionButton("#dcfce7", "#15803d")}>
                        {savingId === campaign.id ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <CheckCircle2 size={14} />}
                        Save
                      </button>
                      <button onClick={() => { setEditingId(null); setDraftText(""); }} style={actionButton("#f8fafc", "#475569")}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button onClick={() => startEdit(campaign)} style={actionButton("#f8fafc", "#0f172a")}>
                      <Sparkles size={14} />
                      Edit
                    </button>
                  )}
                  {campaign.campaign_type === "research_brief" ? (
                    <Link href={`/marketing/generated-content/${campaign.id}?business_id=${campaignBusinessId(campaign)}`} style={linkActionButton("#ede9fe", "#6d28d9")}>
                      <ExternalLink size={14} />
                      Open
                    </Link>
                  ) : (
                    <Link href={`/marketing/generated-content/${campaign.id}?business_id=${campaignBusinessId(campaign)}`} style={linkActionButton("#ede9fe", "#6d28d9")}>
                      <Share2 size={14} />
                      Open
                    </Link>
                  )}
                  <button onClick={() => handleDownload(campaign)} style={actionButton("#fef3c7", "#b45309")}>
                    <Download size={14} />
                    Download
                  </button>
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, color: "#64748b", fontSize: 12 }}>
                  <span>{new Date(campaign.created_at).toLocaleString()}</span>
                  {campaign.scheduled_at && (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Calendar size={13} />
                      {new Date(campaign.scheduled_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function actionButton(background: string, color: string): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: 14,
    border: "none",
    background,
    color,
    cursor: "pointer",
    fontWeight: 700,
    fontSize: 13,
    textDecoration: "none",
  };
}

function linkActionButton(background: string, color: string): React.CSSProperties {
  return {
    ...actionButton(background, color),
    textDecoration: "none",
  };
}
