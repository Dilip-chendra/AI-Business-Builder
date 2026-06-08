"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Calendar,
  CheckCircle2,
  Copy,
  Download,
  Image,
  Loader2,
  Mail,
  Rocket,
  Send,
  Share2,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { useActiveContext } from "@/lib/active-context";
import { cleanDisplayText, truncateClean } from "@/lib/text";
import type { MarketingCampaign } from "@/lib/types";
import { useToast } from "@/components/Toast";

type CampaignAsset = {
  id: string;
  platform?: string;
  asset_type?: string;
  subject?: string;
  content?: Record<string, any>;
  creative_url?: string | null;
  status?: string;
};

function bodyText(campaign?: MarketingCampaign | null, contentOverride?: Record<string, any>) {
  const content = contentOverride || campaign?.content || {};
  return cleanDisplayText(
    content.subject ||
      content.preview_text ||
      content.headline ||
      content.hook ||
      content.post_text ||
      content.body ||
      content.plain_text_body ||
      content.content_markdown ||
      content.executive_summary ||
      content.strategy ||
      content.recommended_angle ||
      (Array.isArray(content.posts) ? content.posts.map((post: any) => post?.text || post?.caption || "").filter(Boolean).join("\n\n") : "") ||
      content
  );
}

function statusTone(status?: string) {
  const normalized = String(status || "draft").toLowerCase();
  if (["approved", "published", "sent", "completed", "scheduled"].includes(normalized)) return { bg: "#dcfce7", color: "#15803d" };
  if (["failed", "rejected"].includes(normalized)) return { bg: "#fee2e2", color: "#dc2626" };
  if (["pending_approval", "draft"].includes(normalized)) return { bg: "#fef3c7", color: "#b45309" };
  return { bg: "#e0e7ff", color: "#4338ca" };
}

function actionErrorMessage(error: any, fallback: string) {
  const detail = error?.detail && typeof error.detail === "object" ? error.detail : {};
  const nextSteps = [
    ...(Array.isArray(error?.next_steps) ? error.next_steps : []),
    ...(Array.isArray(detail?.next_steps) ? detail.next_steps : []),
  ];
  const parts = [
    error?.message,
    detail?.message,
    error?.code || detail?.code ? `Code: ${error?.code || detail?.code}` : "",
    error?.provider || detail?.provider ? `Provider: ${error?.provider || detail?.provider}` : "",
    nextSteps.length ? `Next steps: ${nextSteps.join(" ")}` : "",
  ].filter(Boolean);
  return cleanDisplayText(parts.join(" ")) || fallback;
}

function campaignPlatforms(campaign: MarketingCampaign | null): string[] {
  if (!campaign) return [];
  const assets = Array.isArray(campaign.assets) ? campaign.assets : [];
  const fromAssets = assets.map((asset: CampaignAsset) => String(asset.platform || asset.asset_type || "").toLowerCase()).filter(Boolean);
  const fromTargeting = Array.isArray(campaign.targeting?.platforms)
    ? campaign.targeting.platforms
    : campaign.targeting?.platform
      ? [campaign.targeting.platform]
      : [];
  const fromType = campaign.campaign_type ? [campaign.campaign_type] : [];
  return Array.from(new Set([...fromAssets, ...fromTargeting, ...fromType].map((item) => {
    const value = String(item || "").toLowerCase();
    if (value === "social") return "linkedin";
    if (value === "seo_blog" || value === "blog") return "wordpress";
    return value;
  }).filter((value) => value && value !== "multi_channel" && value !== "research_brief")));
}

export default function CampaignWorkspacePage() {
  const params = useParams<{ campaignId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { active, businesses } = useActiveContext();
  const queryBusinessId = searchParams.get("business_id") || "";
  const [campaign, setCampaign] = useState<MarketingCampaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resolvedBusinessId, setResolvedBusinessId] = useState("");
  const [scheduleAt, setScheduleAt] = useState(() => new Date(Date.now() + 3600_000).toISOString().slice(0, 16));
  const [recipients, setRecipients] = useState("");
  const [draft, setDraft] = useState("");

  const businessId = resolvedBusinessId || queryBusinessId || campaign?.business_id || active.business_id || businesses[0]?.id || "";
  const actionBusinessId = campaign?.business_id || resolvedBusinessId || queryBusinessId || "";
  const status = String(campaign?.lifecycle_status || campaign?.status || "draft").toLowerCase();
  const approved = ["approved", "scheduled", "sent", "published", "completed"].includes(status);
  const platforms = useMemo(() => campaignPlatforms(campaign), [campaign]);
  const tone = statusTone(status);

  async function load() {
    if (!params.campaignId) return;
    setLoading(true);
    try {
      const candidateBusinessIds = Array.from(
        new Set(
          [
            resolvedBusinessId,
            queryBusinessId,
            campaign?.business_id,
            active.business_id,
            ...businesses.map((item) => item.id),
          ].filter(Boolean).map((item) => String(item))
        )
      );
      if (candidateBusinessIds.length === 0) return;
      let row: MarketingCampaign | null = null;
      let lastError: any = null;
      for (const candidate of candidateBusinessIds) {
        try {
          row = await api.getCampaign(candidate, params.campaignId);
          setResolvedBusinessId(String(row.business_id || candidate));
          break;
        } catch (error: any) {
          lastError = error;
        }
      }
      if (!row) throw lastError || new Error("Campaign could not be loaded.");
      setCampaign(row);
      setDraft(bodyText(row));
    } catch (error: any) {
      toast.error(actionErrorMessage(error, "Campaign could not be loaded."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [businessId, params.campaignId]);

  async function approve() {
    if (!campaign || !actionBusinessId) return;
    setApproving(true);
    try {
      const updated = await api.approveCampaign(actionBusinessId, campaign.id);
      setResolvedBusinessId(String(updated.business_id || actionBusinessId));
      setCampaign(updated);
      toast.success("Campaign approved. Publish actions are unlocked.");
    } catch (error: any) {
      toast.error(actionErrorMessage(error, "Campaign approval failed."));
    } finally {
      setApproving(false);
    }
  }

  async function saveDraft() {
    if (!campaign || !actionBusinessId || !draft.trim()) return;
    setSaving(true);
    try {
      const updated = await api.updateCampaign(actionBusinessId, campaign.id, { content_text: draft });
      setResolvedBusinessId(String(updated.business_id || actionBusinessId));
      setCampaign(updated);
      toast.success("Campaign content saved.");
    } catch (error: any) {
      toast.error(actionErrorMessage(error, "Could not save campaign content."));
    } finally {
      setSaving(false);
    }
  }

  async function generateImage() {
    if (!campaign || !actionBusinessId) return;
    setGeneratingImage(true);
    try {
      const result = await api.generateCampaignImage(actionBusinessId, campaign.id);
      setCampaign({ ...campaign, image_url: result.image_url });
      toast.success("Real campaign image generated.");
    } catch (error: any) {
      toast.error(actionErrorMessage(error, "Image generation failed. Configure Hugging Face image generation and retry."));
    } finally {
      setGeneratingImage(false);
    }
  }

  async function publish(platform: string) {
    if (!campaign || !actionBusinessId) return;
    if (!approved) {
      toast.error("Approve this campaign before publishing.");
      return;
    }
    const payload: Record<string, unknown> = {};
    if (platform === "email") {
      const list = recipients.split(",").map((item) => item.trim()).filter(Boolean);
      if (!list.length) {
        toast.error("Enter at least one real recipient before sending email.");
        return;
      }
      payload.recipient_emails = list;
    }
    setPublishing(platform);
    try {
      const result = await api.publishCampaign(actionBusinessId, campaign.id, platform, payload);
      const resultStatus = String(result?.status || "").toLowerCase();
      if (["sent", "published"].includes(resultStatus)) {
        toast.success(cleanDisplayText(result?.message) || `${platform} completed.`);
      } else if (resultStatus === "draft_ready") {
        toast.info(cleanDisplayText(result?.message) || `${platform} draft created. It has not launched.`);
      } else {
        toast.error(cleanDisplayText(result?.message) || `${platform} returned status ${resultStatus || "unknown"}.`);
      }
      await load();
    } catch (error: any) {
      toast.error(actionErrorMessage(error, `${platform} publish failed.`));
    } finally {
      setPublishing(null);
    }
  }

  async function schedule(platform: string) {
    if (!campaign || !actionBusinessId) return;
    if (!approved) {
      toast.error("Approve this campaign before scheduling.");
      return;
    }
    setPublishing(`schedule:${platform}`);
    try {
      await api.scheduleCampaign(actionBusinessId, campaign.id, scheduleAt, Intl.DateTimeFormat().resolvedOptions().timeZone, platform);
      toast.success(`${platform} campaign scheduled.`);
      await load();
    } catch (error: any) {
      toast.error(actionErrorMessage(error, "Scheduling failed."));
    } finally {
      setPublishing(null);
    }
  }

  function browserPublish(platform: string) {
    if (!campaign || !actionBusinessId) return;
    if (!approved) {
      toast.error("Approve this campaign before Browser Agent publishing.");
      return;
    }
    router.push(`/marketing?tab=campaigns&campaign_id=${campaign.id}&action=browser&platform=${platform}&business_id=${actionBusinessId}`);
  }

  async function copyContent() {
    await navigator.clipboard.writeText(draft || bodyText(campaign));
    toast.success("Campaign copy copied.");
  }

  function downloadContent() {
    const blob = new Blob([draft || bodyText(campaign)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${(campaign?.name || "campaign").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return <div style={{ display: "grid", placeItems: "center", minHeight: 520 }}><Loader2 size={34} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} /></div>;
  }

  if (!campaign) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: 520, color: "#475569" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontWeight: 900, color: "#0f172a" }}>Campaign not found</p>
          <Link href="/marketing/generated-content">Back to generated content</Link>
        </div>
      </div>
    );
  }

  const assets = Array.isArray(campaign.assets) ? campaign.assets as CampaignAsset[] : [];
  const imageAssets = assets.filter((asset) => asset.asset_type === "image" || Boolean(asset.creative_url));
  const latestImageAsset = imageAssets[imageAssets.length - 1];
  const imageMeta = latestImageAsset?.content || {};
  const attemptedModels = Array.isArray(imageMeta.models_attempted) ? imageMeta.models_attempted : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      <section style={{ borderRadius: 28, padding: 28, background: "linear-gradient(135deg,#0f172a,#1e1b4b)", color: "#fff", border: "1px solid rgba(148,163,184,0.18)", boxShadow: "0 28px 80px rgba(15,23,42,0.24)" }}>
        <Link href="/marketing/generated-content" style={{ color: "rgba(255,255,255,0.72)", textDecoration: "none", display: "inline-flex", gap: 8, alignItems: "center", fontWeight: 800, fontSize: 13 }}>
          <ArrowLeft size={14} /> Back to content library
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 18, flexWrap: "wrap", marginTop: 18 }}>
          <div style={{ maxWidth: 860 }}>
            <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 900, letterSpacing: "0.14em", textTransform: "uppercase", color: "#a5b4fc" }}>Generated Campaign Workspace</p>
            <h1 style={{ margin: 0, fontSize: 38, lineHeight: 1.06, letterSpacing: "-0.04em" }}>{campaign.name}</h1>
            <p style={{ margin: "12px 0 0", color: "rgba(255,255,255,0.72)", lineHeight: 1.7, maxWidth: 760 }}>{truncateClean(campaign.goal || bodyText(campaign), 240)}</p>
          </div>
          <span style={{ borderRadius: 999, padding: "8px 12px", background: tone.bg, color: tone.color, fontSize: 12, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.08em" }}>{status.replace(/_/g, " ")}</span>
        </div>
      </section>

      {!approved && (
        <div style={{ borderRadius: 18, border: "1px solid #fde68a", background: "#fffbeb", padding: 16, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
          <div>
            <p style={{ margin: "0 0 4px", color: "#92400e", fontWeight: 900 }}>Approval required</p>
            <p style={{ margin: 0, color: "#a16207", fontSize: 13 }}>No live send, API publish, browser publish, or schedule action will run until you approve this campaign.</p>
          </div>
          <button onClick={approve} disabled={approving} style={button("#16a34a", "#fff")}>{approving ? <Loader2 size={14} /> : <CheckCircle2 size={14} />} Approve Campaign</button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.35fr) minmax(320px, 0.65fr)", gap: 20 }}>
        <main style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <section style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 12 }}>
              <h2 style={sectionTitle}>Campaign Copy</h2>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={copyContent} style={ghostButton("#eef2ff", "#4338ca")}><Copy size={14} /> Copy</button>
                <button onClick={downloadContent} style={ghostButton("#fef3c7", "#b45309")}><Download size={14} /> Export</button>
                <button onClick={saveDraft} disabled={saving} style={button("#4f46e5", "#fff")}>{saving ? <Loader2 size={14} /> : <Sparkles size={14} />} Save</button>
              </div>
            </div>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={16} style={{ width: "100%", resize: "vertical", minHeight: 360, border: "1px solid #cbd5e1", borderRadius: 18, padding: 16, color: "#0f172a", background: "#f8fafc", fontSize: 14, lineHeight: 1.75, fontFamily: "inherit", outline: "none" }} />
          </section>

          {assets.length > 0 && (
            <section style={cardStyle}>
              <h2 style={sectionTitle}>Platform Assets</h2>
              <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
                {assets.map((asset) => (
                  <div key={asset.id} style={{ border: "1px solid #e2e8f0", borderRadius: 18, padding: 16, background: "#f8fafc" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
                      <p style={{ margin: 0, color: "#0f172a", fontWeight: 900, textTransform: "capitalize" }}>{asset.platform || asset.asset_type || "Asset"}</p>
                      <span style={{ color: "#64748b", fontSize: 12, fontWeight: 800 }}>{asset.status || "draft"}</span>
                    </div>
                    <p style={{ margin: 0, color: "#475569", fontSize: 13, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>{truncateClean(bodyText(campaign, asset.content), 900)}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>

        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section style={cardStyle}>
            <h2 style={sectionTitle}>Creative</h2>
            {(campaign.image_url || campaign.content?.image_url) ? (
              <img src={campaign.image_url || campaign.content?.image_url} alt="Campaign creative" style={{ width: "100%", borderRadius: 18, border: "1px solid #e2e8f0", marginTop: 12 }} />
            ) : (
              <div style={{ border: "1px dashed #cbd5e1", borderRadius: 18, padding: 22, color: "#64748b", marginTop: 12, fontSize: 13 }}>No generated campaign image yet.</div>
            )}
            <button onClick={generateImage} disabled={generatingImage} style={{ ...button("#111827", "#fff"), marginTop: 12, width: "100%", justifyContent: "center" }}>{generatingImage ? <Loader2 size={14} /> : <Image size={14} />} Generate Image</button>
            <div style={{ marginTop: 12, borderRadius: 16, border: "1px solid #dbeafe", background: "#eff6ff", padding: 12, color: "#1e3a8a", fontSize: 12, lineHeight: 1.55 }}>
              <p style={{ margin: "0 0 6px", fontWeight: 900 }}>Image provider: Hugging Face</p>
              <p style={{ margin: 0 }}>Model: {cleanDisplayText(imageMeta.model || "HUGGINGFACE_IMAGE_MODEL, then SDXL / SD v1.5 / OpenJourney / SSD-1B fallbacks")}</p>
              {attemptedModels.length > 0 && (
                <p style={{ margin: "6px 0 0", color: "#2563eb" }}>Attempted: {attemptedModels.map((model) => cleanDisplayText(model)).join(", ")}</p>
              )}
            </div>
          </section>

          <section style={cardStyle}>
            <h2 style={sectionTitle}>Publishing Console</h2>
            {platforms.includes("email") && (
              <label style={{ display: "grid", gap: 7, marginTop: 12 }}>
                <span style={labelStyle}>Email recipients</span>
                <textarea value={recipients} onChange={(event) => setRecipients(event.target.value)} placeholder="customer@example.com, lead@example.com" rows={3} style={inputStyle} />
              </label>
            )}
            <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
              {(platforms.length ? platforms : ["linkedin"]).map((platform) => (
                <div key={platform} style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: 12, background: "#f8fafc", display: "grid", gap: 10 }}>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 900, color: "#0f172a", textTransform: "capitalize" }}>{platform.replace(/_/g, " ")}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button onClick={() => publish(platform)} disabled={publishing === platform || !approved} style={smallButton("#4f46e5", "#fff", !approved)}>{publishing === platform ? <Loader2 size={13} /> : platform === "email" ? <Mail size={13} /> : <Send size={13} />} API</button>
                    {["linkedin", "twitter", "instagram", "facebook", "wordpress", "email"].includes(platform) && (
                      <button onClick={() => browserPublish(platform)} disabled={!approved} style={smallButton("#0f172a", "#fff", !approved)}><Bot size={13} /> Browser</button>
                    )}
                    <button onClick={() => schedule(platform)} disabled={publishing === `schedule:${platform}` || !approved} style={smallButton("#f59e0b", "#fff", !approved)}>{publishing === `schedule:${platform}` ? <Loader2 size={13} /> : <Calendar size={13} />} Schedule</button>
                  </div>
                </div>
              ))}
            </div>
            <label style={{ display: "grid", gap: 7, marginTop: 14 }}>
              <span style={labelStyle}>Schedule time</span>
              <input type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)} style={inputStyle} />
            </label>
          </section>

          <section style={cardStyle}>
            <h2 style={sectionTitle}>Real Action Rules</h2>
            <div style={{ display: "grid", gap: 9, marginTop: 12, color: "#475569", fontSize: 13, lineHeight: 1.55 }}>
              <p style={{ margin: 0 }}><Rocket size={13} /> API publish requires a connected provider and only marks success after provider confirmation.</p>
              <p style={{ margin: 0 }}><Bot size={13} /> Browser Agent stops at login, missing composer, or final review instead of pretending success.</p>
              <p style={{ margin: 0 }}><Share2 size={13} /> Metrics stay zero until real events arrive.</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

const cardStyle = {
  borderRadius: 24,
  background: "#fff",
  border: "1px solid #e2e8f0",
  padding: 20,
  boxShadow: "0 18px 50px rgba(15,23,42,0.07)",
} as const;

const sectionTitle = {
  margin: 0,
  fontSize: 15,
  color: "#0f172a",
  fontWeight: 900,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
} as const;

const labelStyle = { fontSize: 12, fontWeight: 900, color: "#334155" } as const;

const inputStyle = {
  width: "100%",
  border: "1px solid #cbd5e1",
  borderRadius: 14,
  padding: "11px 12px",
  color: "#0f172a",
  background: "#fff",
  fontSize: 13,
  fontFamily: "inherit",
} as const;

function button(background: string, color: string) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    border: "none",
    borderRadius: 14,
    padding: "11px 14px",
    background,
    color,
    fontWeight: 900,
    cursor: "pointer",
    fontFamily: "inherit",
  } as const;
}

function ghostButton(background: string, color: string) {
  return { ...button(background, color), border: "1px solid rgba(148,163,184,0.24)" } as const;
}

function smallButton(background: string, color: string, disabled = false) {
  return {
    ...button(disabled ? "#cbd5e1" : background, disabled ? "#64748b" : color),
    padding: "8px 10px",
    borderRadius: 11,
    fontSize: 12,
    cursor: disabled ? "not-allowed" : "pointer",
  } as const;
}
