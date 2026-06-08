"use client";
import NextLink from "next/link";
import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bot, Sparkles, Play, Square, Mail, Share2, Megaphone, Globe, Loader2,
  CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronRight, Plus,
  RefreshCw, Target, TrendingUp, BarChart3, Calendar, Settings, Zap,
  Image, Send, Link as LinkIcon, Twitter, Linkedin, Facebook, Instagram, Youtube,
} from "lucide-react";
import { api } from "@/lib/api";
import { useActiveContext } from "@/lib/active-context";
import { cleanDisplayText, truncateClean } from "@/lib/text";
import { useToast } from "@/components/Toast";
import { JobProgress } from "@/components/JobProgress";
import { IntegrationAccountModal, type IntegrationAccountModalState } from "@/components/marketing/IntegrationAccountModal";
import useJobStart from "@/hooks/useJobStart";
import type { IntegrationAccount, IntegrationStatus, MarketingCampaign, Product } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function useIsMobile(breakpoint = 1200) {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < breakpoint);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [breakpoint]);
  return isMobile;
}

function actionErrorMessage(error: any, fallback: string) {
  const parts = [
    error?.message,
    error?.detail,
    error?.code ? `Code: ${error.code}` : "",
    Array.isArray(error?.next_steps) && error.next_steps.length
      ? `Next steps: ${error.next_steps.join(" ")}`
      : "",
    String(error || ""),
  ].filter(Boolean);
  return cleanDisplayText(parts.join(" ")) || fallback;
}

function isRealSuccessStatus(status?: string) {
  return ["sent", "published", "scheduled", "completed"].includes(String(status || "").toLowerCase());
}

// â”€â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
type AgentEvent = {
  type: string;
  agent?: string;
  message: string;
  data?: any;
  step?: number;
  total_steps?: number;
};

type BrowserPreview = {
  platform: string;
  status: string;
  screenshot?: string;
  url?: string;
  title?: string;
  lastAction?: string;
  summary?: string;
  step?: number;
};

type PublishDetailsModalState = {
  campaignId: string;
  platform: string;
  title: string;
  fields: Array<{ key: string; label: string; placeholder: string; required?: boolean }>;
  values: Record<string, string>;
};

type IntegrationActionLog = {
  id: string;
  provider: string;
  action: string;
  status: string;
  message?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
};

type BrandSystem = {
  primary_color: string;
  secondary_color: string;
  tone_of_voice: string;
  target_audience: string;
  industry: string;
  competitors: string[];
  website_url: string;
  logo_description: string;
};

type AnalyticsData = {
  total_impressions: number;
  total_clicks: number;
  total_conversions: number;
  total_spend_cents: number;
  total_revenue_usd: number;
  ctr: number;
  campaigns: Array<{
    id: string;
    name: string;
    type: string;
    impressions: number;
    clicks: number;
    ctr: number;
    conversions: number;
    spend_cents: number;
    revenue_usd?: number;
    analytics_source?: string;
  }>;
  insights?: string[];
};

type CalendarPost = {
  id: string;
  campaign_id: string;
  platform: string;
  content_json?: string;
  scheduled_at_utc: string;
  status: string;
  title?: string;
  description?: string;
  source?: string;
  campaign_name?: string;
};

type ContactRow = {
  id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  source: string;
  consent_status: string;
  segment?: string | null;
  lead_status: string;
  lead_score: number;
};

type Tab = "engine" | "campaigns" | "content-studio" | "analytics" | "integrations" | "calendar";

// â”€â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  draft:            { bg: "#f1f5f9", color: "#64748b" },
  pending_approval: { bg: "#fef3c7", color: "#d97706" },
  approved:         { bg: "#dcfce7", color: "#16a34a" },
  sent:             { bg: "#dbeafe", color: "#2563eb" },
  rejected:         { bg: "#fee2e2", color: "#dc2626" },
  published:        { bg: "#dcfce7", color: "#16a34a" },
  scheduled:        { bg: "#e0e7ff", color: "#4f46e5" },
  running:          { bg: "#dbeafe", color: "#2563eb" },
  paused:           { bg: "#fef3c7", color: "#d97706" },
  completed:        { bg: "#dcfce7", color: "#16a34a" },
  failed:           { bg: "#fee2e2", color: "#dc2626" },
  awaiting_final_confirmation: { bg: "#dbeafe", color: "#1d4ed8" },
  pending_publish:  { bg: "#e0e7ff", color: "#4f46e5" },
};

const AGENT_COLORS: Record<string, string> = {
  OpsAgent:          "#22c55e",
  StrategyAgent:     "#6366f1",
  ContentAgent:      "#0ea5e9",
  CreativeAgent:     "#8b5cf6",
  CampaignAgent:     "#10b981",
  AnalyticsAgent:    "#f59e0b",
  OptimizationAgent: "#ef4444",
  PublishPlannerAgent: "#14b8a6",
};

function showOptimizationToast(result: any, toast: ReturnType<typeof useToast>) {
  if (result?.optimization_mode === "content_review") {
    const headline = result?.headline_suggestion || result?.cta_suggestion || "AI content optimization is ready.";
    toast.info(`Content optimization: ${headline}`);
    return;
  }
  const headline = result?.headline_suggestion || result?.cta_suggestion || result?.next_test || "Optimization recommendations are ready.";
  toast.info(`Optimization: ${headline}`);
}

const PLATFORM_CHIPS = [
  { id: "email",      label: "Email" },
  { id: "linkedin",   label: "LinkedIn" },
  { id: "twitter",    label: "Twitter" },
  { id: "instagram",  label: "Instagram" },
  { id: "facebook",   label: "Facebook" },
  { id: "google_ads", label: "Google Ads" },
  { id: "meta_ads",   label: "Meta Ads" },
  { id: "wordpress",  label: "WordPress" },
];

const QUICK_GOALS = [
  "Book more HVAC tune-up appointments this month",
  "Generate plumbing emergency service leads",
  "Launch a roofing inspection offer before storm season",
  "Win electrical panel upgrade calls from homeowners",
  "Increase sales by 20% this month",
  "Launch new product to existing customers",
  "Re-engage inactive users with special offer",
  "Build brand awareness in new market",
  "Drive sign-ups for upcoming webinar",
];

const BROWSER_PUBLISH_PLATFORMS = new Set(["email", "linkedin", "twitter", "instagram", "facebook", "wordpress"]);

const CONTENT_TYPES = [
  { id: "linkedin_post",      label: "LinkedIn Post" },
  { id: "twitter_thread",     label: "Twitter Thread" },
  { id: "instagram_caption",  label: "Instagram Caption" },
  { id: "email_sequence",     label: "Email Sequence" },
  { id: "blog_post",          label: "Blog Post" },
  { id: "ad_copy",            label: "Ad Copy" },
  { id: "youtube_description",label: "YouTube Description" },
];

const TONES = ["Professional", "Casual", "Humorous", "Inspirational", "Urgent"];
const CTAS  = ["Learn More", "Buy Now", "Sign Up", "Book a Demo", "Download"];

const INTEGRATION_PLATFORMS = [
  { id: "linkedin",   label: "LinkedIn",    icon: "in",  color: "#0077b5", apiKey: false },
  { id: "gmail",      label: "Gmail",       icon: "G",   color: "#ea4335", apiKey: false, oauthProvider: "google" },
  { id: "twitter",    label: "Twitter / X", icon: "X",   color: "#000000", apiKey: false },
  { id: "facebook",   label: "Facebook",    icon: "f",   color: "#1877f2", apiKey: false },
  { id: "instagram",  label: "Instagram",   icon: "IG",  color: "#e1306c", apiKey: false },
  { id: "slack",      label: "Slack",       icon: "S",   color: "#4a154b", apiKey: false },
  { id: "notion",     label: "Notion",      icon: "N",   color: "#111827", apiKey: false },
  { id: "google_ads", label: "Google Ads",  icon: "G",   color: "#4285f4", apiKey: false },
  { id: "meta_ads",   label: "Meta Ads",    icon: "M",   color: "#0668e1", apiKey: false },
  { id: "sendgrid",   label: "SendGrid",    icon: "SG",  color: "#1a82e2", apiKey: false },
  { id: "wordpress",  label: "WordPress",   icon: "WP",  color: "#21759b", apiKey: false },
];

const AGENTIC_PLAYBOOKS = [
  {
    label: "Home Services Lead Engine",
    goal: "Create a local home services growth campaign with lead capture, fast follow-up email, LinkedIn/local social proof posts, review request messaging, and appointment CTA. Use HVAC, plumbing, electrical, or roofing positioning depending on the selected business.",
    platforms: ["email", "linkedin", "wordpress"],
  },
  {
    label: "Revenue Launch",
    goal: "Build a full revenue launch sequence with email, social proof posts, ad drafts, and follow-up recommendations",
    platforms: ["email", "social", "google_ads"],
  },
  {
    label: "Audience Growth",
    goal: "Create an audience growth campaign that turns educational content into social posts, lead capture emails, and retargeting ad drafts",
    platforms: ["social", "email", "meta_ads"],
  },
  {
    label: "Content Engine",
    goal: "Create a weekly content engine with SEO blog ideas, social repurposing, and email newsletter assets",
    platforms: ["wordpress", "social", "email"],
  },
];

const ACCOUNT_VAULT_PLATFORMS = [
  { id: "linkedin", label: "LinkedIn Browser Session", hint: "Used for LinkedIn posting and draft verification." },
  { id: "instagram", label: "Instagram Browser Session", hint: "Used for Instagram posting workflows and media drafts." },
  { id: "facebook", label: "Facebook Browser Session", hint: "Used for Facebook Page posting and Meta checkpoints." },
  { id: "twitter", label: "Twitter / X Browser Session", hint: "Used for X posting workflows when OAuth is not configured." },
  { id: "wordpress", label: "WordPress Browser Session", hint: "Used for WordPress post drafts and publish verification." },
  { id: "gmail", label: "Gmail Browser Session", hint: "Used for Gmail send/review workflows when browser automation is needed." },
  { id: "browser_automation", label: "Generic Browser Operator", hint: "Fallback account for shared browser login flows and verification tasks." },
];

// â”€â”€â”€ Small helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.draft;
  return (
    <span style={{ background: s.bg, color: s.color, fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 99, whiteSpace: "nowrap" }}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function MetricBadge({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", background: `${color}15`, borderRadius: 8, padding: "6px 10px", minWidth: 56 }}>
      <span style={{ fontSize: 14, fontWeight: 800, color }}>{value}</span>
      <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600 }}>{label}</span>
    </div>
  );
}

function PlatformIcon({ platform, size = 28 }: { platform: string; size?: number }) {
  const cfg = INTEGRATION_PLATFORMS.find(p => p.id === platform);
  if (!cfg) return <div style={{ width: size, height: size, borderRadius: 8, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800, color: "#64748b" }}>?</div>;
  return (
    <div style={{ width: size, height: size, borderRadius: 8, background: cfg.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: Math.floor(size * 0.4), fontWeight: 900, color: "#fff", flexShrink: 0 }}>
      {cfg.icon}
    </div>
  );
}

function campaignTypeConfig(type: string) {
  const map: Record<string, { icon: any; bg: string; color: string; label: string }> = {
    email:     { icon: Mail,     bg: "#dbeafe", color: "#2563eb", label: "Email" },
    social:    { icon: Share2,   bg: "#ede9fe", color: "#7c3aed", label: "Social" },
    linkedin:  { icon: Linkedin, bg: "#dbeafe", color: "#0077b5", label: "LinkedIn" },
    twitter:   { icon: Twitter,  bg: "#e0f2fe", color: "#0ea5e9", label: "Twitter" },
    instagram: { icon: Instagram,bg: "#fce7f3", color: "#e1306c", label: "Instagram" },
    facebook:  { icon: Facebook, bg: "#dbeafe", color: "#1877f2", label: "Facebook" },
    google_ads:{ icon: Megaphone,bg: "#fef3c7", color: "#d97706", label: "Google Ads" },
    meta_ads:  { icon: Megaphone,bg: "#fce7f3", color: "#db2777", label: "Meta Ads" },
    seo_blog:  { icon: Globe,    bg: "#dcfce7", color: "#16a34a", label: "SEO Blog" },
    research_brief: { icon: Sparkles, bg: "#eef2ff", color: "#4f46e5", label: "Research Brief" },
  };
  return map[type] || map.email;
}

function campaignPlatform(campaign: MarketingCampaign) {
  return String(
    campaign.targeting?.platform ||
    campaign.content?.platform ||
    campaign.content?.channel ||
    campaign.campaign_type ||
    ""
  ).toLowerCase();
}

function campaignDisplayConfig(campaign: MarketingCampaign) {
  const platform = campaignPlatform(campaign);
  if (campaign.campaign_type === "social" && ["linkedin", "twitter", "instagram", "facebook"].includes(platform)) {
    return campaignTypeConfig(platform);
  }
  return campaignTypeConfig(campaign.campaign_type);
}

function socialPublishConfig(campaign: MarketingCampaign) {
  const platform = campaignPlatform(campaign);
  const map: Record<string, { platform: string; label: string; icon: any; bg: string; softBg: string; softColor: string; softBorder: string }> = {
    linkedin: {
      platform: "linkedin",
      label: "Post to LinkedIn",
      icon: Linkedin,
      bg: "#0077b5",
      softBg: "rgba(0,119,181,0.15)",
      softColor: "#7dd3fc",
      softBorder: "1px solid rgba(0,119,181,0.3)",
    },
    twitter: {
      platform: "twitter",
      label: "Post to Twitter",
      icon: Twitter,
      bg: "#000",
      softBg: "rgba(0,0,0,0.2)",
      softColor: "#94a3b8",
      softBorder: "1px solid rgba(255,255,255,0.1)",
    },
    instagram: {
      platform: "instagram",
      label: "Publish to Instagram",
      icon: Instagram,
      bg: "#e1306c",
      softBg: "rgba(225,48,108,0.15)",
      softColor: "#f9a8d4",
      softBorder: "1px solid rgba(225,48,108,0.3)",
    },
    facebook: {
      platform: "facebook",
      label: "Post to Facebook",
      icon: Facebook,
      bg: "#1877f2",
      softBg: "rgba(24,119,242,0.15)",
      softColor: "#93c5fd",
      softBorder: "1px solid rgba(24,119,242,0.3)",
    },
  };
  return map[platform] || map.linkedin;
}

function campaignActionPlatforms(campaign: MarketingCampaign): string[] {
  const raw = Array.isArray(campaign.targeting?.platforms)
    ? campaign.targeting.platforms
    : campaign.targeting?.platform
      ? [campaign.targeting.platform]
      : [];
  const normalized = raw.map((item: string) => {
    const value = String(item || "").toLowerCase();
    if (value === "social") return "twitter";
    if (value === "seo_blog" || value === "blog") return "wordpress";
    return value;
  }).filter(Boolean);
  return Array.from(new Set(normalized));
}

function effectiveCampaignStatus(campaign: MarketingCampaign): string {
  const status = String(campaign.status || "").toLowerCase();
  const lifecycle = String(campaign.lifecycle_status || "").toLowerCase();
  const terminal = ["published", "sent", "completed", "scheduled", "sending", "failed", "paused", "awaiting_final_confirmation"];
  const approved = ["approved"];
  for (const value of [status, lifecycle]) {
    if (terminal.includes(value)) return value;
  }
  for (const value of [status, lifecycle]) {
    if (approved.includes(value)) return value;
  }
  if ([status, lifecycle].includes("pending_approval") || [status, lifecycle].includes("pending approval")) return "pending_approval";
  if ([status, lifecycle].includes("rejected")) return "rejected";
  return status || lifecycle || "draft";
}

function integrationStateMeta(item?: IntegrationStatus) {
  const label = item?.state_label || item?.status || "disconnected";
  const map: Record<string, { bg: string; color: string; title: string }> = {
    connected: { bg: "#dcfce7", color: "#16a34a", title: "Connected" },
    ready_to_connect: { bg: "#dbeafe", color: "#2563eb", title: "Ready to connect" },
    not_configured: { bg: "#fef3c7", color: "#d97706", title: "Not configured" },
    expired: { bg: "#fee2e2", color: "#dc2626", title: "Needs reconnect" },
    disconnected: { bg: "#f1f5f9", color: "#64748b", title: "Disconnected" },
    error: { bg: "#fee2e2", color: "#dc2626", title: "Error" },
  };
  return map[label] || map.disconnected;
}

function extractContentText(campaign: MarketingCampaign | null) {
  if (!campaign?.content) return "";
  const content = campaign.content;
  return cleanDisplayText(
    content.subject ||
    content.executive_summary ||
    content.recommended_angle ||
    content.preview_text ||
    content.headline ||
    content.post_text ||
    content.body ||
    content.plain_text_body ||
    content.content_markdown ||
    (Array.isArray(content.posts) ? content.posts.map((post: any) => post?.text || post?.caption || "").filter(Boolean).join("\n\n") : "") ||
    ""
  );
}

function renderContentPreview(campaign: MarketingCampaign) {
  const content = campaign.content || {};
  const text = extractContentText(campaign);
  if (campaign.campaign_type === "email") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ border: "1px solid #dbeafe", background: "#f8fbff", borderRadius: 12, padding: 14 }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Email Preview</p>
          <p style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>{cleanDisplayText(content.subject || "Untitled email")}</p>
          <p style={{ fontSize: 12, color: "#64748b", margin: "0 0 10px" }}>{cleanDisplayText(content.preview_text || "")}</p>
          <div className="marketing-scroll marketing-scroll--soft" style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, fontSize: 13, color: "#374151", lineHeight: 1.7, maxHeight: 180, overflowY: "auto" }}>
            {truncateClean(cleanDisplayText(content.plain_text_body || text), 700)}
          </div>
        </div>
      </div>
    );
  }
  if (campaign.campaign_type === "seo_blog") {
    return (
      <div style={{ border: "1px solid #dcfce7", background: "#f6fff8", borderRadius: 12, padding: 14 }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>SEO Blog Preview</p>
        <p style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>{cleanDisplayText(content.title || campaign.name)}</p>
        <p style={{ fontSize: 12, color: "#64748b", margin: "0 0 10px" }}>{cleanDisplayText(content.meta_description || "")}</p>
        <div className="marketing-scroll marketing-scroll--soft" style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, fontSize: 13, color: "#374151", lineHeight: 1.7, maxHeight: 180, overflowY: "auto" }}>
          {truncateClean(cleanDisplayText(content.content_markdown || text), 700)}
        </div>
      </div>
    );
  }
  if (campaign.campaign_type === "google_ads" || campaign.campaign_type === "meta_ads") {
    return (
      <div style={{ border: "1px solid #fde68a", background: "#fffdf6", borderRadius: 12, padding: 14 }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#d97706", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Ads Preview</p>
        <p style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>{cleanDisplayText(content.campaign_name || campaign.name)}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {(content.ad_creatives || []).slice(0, 2).map((creative: any, index: number) => (
            <div key={index} style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12 }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>{cleanDisplayText(creative.headline || `Creative ${index + 1}`)}</p>
              <p style={{ fontSize: 12, color: "#475569", margin: 0 }}>{cleanDisplayText(creative.description || "")}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (campaign.campaign_type === "research_brief") {
    const keywords = Array.isArray(content.keywords) ? content.keywords.slice(0, 8) : [];
    const pricing = Array.isArray(content.pricing_signals) ? content.pricing_signals.slice(0, 5) : [];
    const entities = Array.isArray(content.competitor_or_entity_signals) ? content.competitor_or_entity_signals.slice(0, 6) : [];
    const evidence = Array.isArray(content.evidence) ? content.evidence.slice(0, 2) : [];
    return (
      <div style={{ border: "1px solid #c7d2fe", background: "#f8faff", borderRadius: 12, padding: 14 }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#4f46e5", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Research Brief</p>
        <p style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 8px" }}>{cleanDisplayText(content.recommended_angle || content.goal || campaign.name)}</p>
        <div className="marketing-scroll marketing-scroll--soft" style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, fontSize: 13, color: "#374151", lineHeight: 1.7, maxHeight: 160, overflowY: "auto", whiteSpace: "pre-wrap" }}>
          {truncateClean(cleanDisplayText(content.executive_summary || text), 650)}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {[...keywords, ...pricing, ...entities].slice(0, 14).map((item: string, index: number) => (
            <span key={`${item}-${index}`} style={{ borderRadius: 999, background: index < keywords.length ? "#dbeafe" : "#fef3c7", color: index < keywords.length ? "#1d4ed8" : "#b45309", padding: "4px 8px", fontSize: 10, fontWeight: 800 }}>
              {truncateClean(cleanDisplayText(String(item)), 34)}
            </span>
          ))}
        </div>
        {evidence.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {evidence.map((item: any, index: number) => (
              <p key={index} style={{ margin: 0, color: "#64748b", fontSize: 11, lineHeight: 1.5 }}>
                {truncateClean(cleanDisplayText(item.title || item.url || "Evidence source"), 90)}
              </p>
            ))}
          </div>
        )}
      </div>
    );
  }
  return (
    <div style={{ border: "1px solid #ede9fe", background: "#faf7ff", borderRadius: 12, padding: 14 }}>
      <p style={{ fontSize: 11, fontWeight: 700, color: "#7c3aed", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Social Preview</p>
      <div className="marketing-scroll marketing-scroll--soft" style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, fontSize: 13, color: "#374151", lineHeight: 1.7, maxHeight: 180, overflowY: "auto", whiteSpace: "pre-wrap" }}>
        {truncateClean(text, 700) || "No content preview available yet."}
      </div>
    </div>
  );
}

import { ErrorBoundary } from "@/components/ErrorBoundary";

// â”€â”€â”€ Main Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function MarketingPageInner() {
  const isMobile = useIsMobile();
  const isCompactDesktop = useIsMobile(1480);
  const toast = useToast();
  const searchParams = useSearchParams();
  const { businesses: contextBusinesses, active, setActiveContext } = useActiveContext();
  // Core state
  const businesses = contextBusinesses.map((b) => ({ id: b.id, name: b.name }));
  const [businessId, setBusinessIdState] = useState(active.business_id || "");
  const currentBusinessName = businesses.find((item) => item.id === businessId)?.name || "this business";
  const [tab, setTab] = useState<Tab>("engine");
  const [error, setError] = useState<string | null>(null);

  // Engine tab
  const [goal, setGoal] = useState("");
  const [budget, setBudget] = useState("100");
  const [platforms, setPlatforms] = useState<string[]>(["email", "linkedin", "twitter"]);
  const [running, setRunning] = useState(false);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [browserPreview, setBrowserPreview] = useState<BrowserPreview | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const contactFileInputRef = useRef<HTMLInputElement>(null);

  // Campaigns tab
  const [campaigns, setCampaigns] = useState<MarketingCampaign[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [generatingImage, setGeneratingImage] = useState<string | null>(null);
  const [cardImages, setCardImages] = useState<Record<string, string>>({});

  // Content Studio tab
  const [contentType, setContentType] = useState("linkedin_post");
  const [tone, setTone] = useState("Professional");
  const [audience, setAudience] = useState("");
  const [cta, setCta] = useState("Learn More");
  const [contentGoal, setContentGoal] = useState("");
  const [generatingContent, setGeneratingContent] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<any | null>(null);

  // Analytics tab
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Integrations tab
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationAccounts, setIntegrationAccounts] = useState<Record<string, IntegrationAccount>>({});
  const [integrationAccountsLoading, setIntegrationAccountsLoading] = useState(false);
  const [integrationLogs, setIntegrationLogs] = useState<IntegrationActionLog[]>([]);
  const [integrationLogsLoading, setIntegrationLogsLoading] = useState(false);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [testingOAuth, setTestingOAuth] = useState<string | null>(null);
  const [refreshingOAuth, setRefreshingOAuth] = useState<string | null>(null);
  const [accountModal, setAccountModal] = useState<IntegrationAccountModalState | null>(null);
  const [savingAccount, setSavingAccount] = useState<string | null>(null);
  const [testingAccount, setTestingAccount] = useState<string | null>(null);
  const [deletingAccount, setDeletingAccount] = useState<string | null>(null);
  const [emailSendModal, setEmailSendModal] = useState<{ campaignId: string; recipients: string } | null>(null);
  const [publishDetailsModal, setPublishDetailsModal] = useState<PublishDetailsModalState | null>(null);
  const [scheduleModal, setScheduleModal] = useState<{ campaignId: string; platform: string; scheduledAt: string } | null>(null);
  const [rejectModal, setRejectModal] = useState<{ campaignId: string; reason: string } | null>(null);
  const [browserRun, setBrowserRun] = useState<{ runId: string; campaignId: string; platform: string; awaitingConfirmation: boolean } | null>(null);
  const [confirmingPublish, setConfirmingPublish] = useState(false);

  // Calendar tab
  const [calendarPosts, setCalendarPosts] = useState<CalendarPost[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [contacts, setContacts] = useState<ContactRow[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [importingContacts, setImportingContacts] = useState(false);
  const [syncingCalendar, setSyncingCalendar] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState("");

  // Brand settings panel
  const [brandPanelOpen, setBrandPanelOpen] = useState(false);
  const [brand, setBrand] = useState<BrandSystem>({
    primary_color: "#6366f1",
    secondary_color: "#8b5cf6",
    tone_of_voice: "professional",
    target_audience: "",
    industry: "",
    competitors: [],
    website_url: "",
    logo_description: "",
  });
  const [competitorsInput, setCompetitorsInput] = useState("");
  const [savingBrand, setSavingBrand] = useState(false);
  const [brandSaved, setBrandSaved] = useState(false);
  const handledOauthRedirectRef = useRef<string | null>(null);
  const autoActionRef = useRef<string | null>(null);

  // Job tracking
  const [jobId, setJobId] = useState<string | null>(null);
  const { startSeoBlogJob, startEmailCampaignJob } = useJobStart();

  useEffect(() => {
    const businessParam = searchParams.get("business_id") || "";
    if (businessParam) {
      return;
    }
    if (active.business_id && active.business_id !== businessId) {
      setBusinessIdState(active.business_id);
    }
  }, [active.business_id, businessId, searchParams]);

  useEffect(() => {
    const businessParam = searchParams.get("business_id") || "";
    const productId = searchParams.get("product_id") || "";
    const goalParam = searchParams.get("goal") || "";
    const tabParam = (searchParams.get("tab") || "").toLowerCase();
    const campaignIdParam = searchParams.get("campaign_id") || "";
    const actionParam = (searchParams.get("action") || "").toLowerCase();
    const platformParam = (searchParams.get("platform") || "").toLowerCase();
    if (businessParam && businessParam !== businessId) {
      setBusinessId(businessParam);
    }
    if (productId) {
      setSelectedProductId(productId);
    }
    if (goalParam && !goal.trim()) {
      setGoal(goalParam);
      setContentGoal(goalParam);
    }
    if (tabParam === "campaigns" || tabParam === "content-studio" || tabParam === "analytics" || tabParam === "integrations" || tabParam === "calendar" || tabParam === "engine") {
      setTab(tabParam as Tab);
    }
    if (campaignIdParam) {
      setExpanded(campaignIdParam);
    }
    if (campaignIdParam && actionParam) {
      autoActionRef.current = `${campaignIdParam}:${actionParam}:${platformParam}`;
    }
  }, [searchParams]);

  useEffect(() => {
    if (!autoActionRef.current || campaigns.length === 0 || !businessId) {
      return;
    }
    const [campaignId, actionName, requestedPlatform] = autoActionRef.current.split(":");
    const campaign = campaigns.find((item) => item.id === campaignId);
    if (!campaign) {
      return;
    }
    setTab("campaigns");
    setExpanded(campaignId);
    if (actionName === "publish" && (campaign.lifecycle_status === "approved" || campaign.status === "approved")) {
      autoActionRef.current = null;
      const platform = requestedPlatform || String(campaign.targeting?.platform || campaign.content?.platform || "linkedin");
      handlePublish(campaignId, platform).catch((err) => {
        setError(err?.message || "Could not start the publish workflow.");
      });
    }
    if (actionName === "browser" && (campaign.lifecycle_status === "approved" || campaign.status === "approved")) {
      autoActionRef.current = null;
      const platform = requestedPlatform || String(campaign.targeting?.platform || campaign.content?.platform || "linkedin");
      handlePublish(campaignId, `${platform}_browser`).catch((err) => {
        setError(err?.message || "Could not start the browser workflow.");
      });
    }
  }, [campaigns, businessId]);

  useEffect(() => {
    const oauthStatus = searchParams.get("oauth");
    const provider = searchParams.get("provider");
    const message = searchParams.get("message");
    if (!oauthStatus || handledOauthRedirectRef.current === `${oauthStatus}:${provider}:${message}`) {
      return;
    }
    handledOauthRedirectRef.current = `${oauthStatus}:${provider}:${message}`;
    setTab("integrations");
    if (oauthStatus === "success") {
      toast.success(cleanDisplayText(message || `${provider || "Provider"} connected successfully.`));
      loadIntegrations().catch(console.error);
    } else {
      toast.error(cleanDisplayText(message || `Could not connect ${provider || "provider"}.`));
    }

    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      ["oauth", "provider", "message"].forEach((key) => url.searchParams.delete(key));
      window.history.replaceState({}, "", url.toString());
    }
  }, [searchParams, toast, businessId]);

  const setBusinessId = (value: string) => {
    setBusinessIdState(value);
    setActiveContext({ business_id: value, project_id: null }).catch(console.error);
  };

  useEffect(() => {
    if (active.business_id) {
      setBusinessId(active.business_id);
      return;
    }
    if (!businessId && businesses[0]) {
      setBusinessId(businesses[0].id);
    }
  }, [active.business_id, businessId, businesses]);

  // â”€â”€ When business changes: reload everything â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (!businessId) return;
    loadCampaigns();
    loadIntegrations();
    loadIntegrationAccounts();
    loadAnalytics();
    loadCalendar();
    loadContacts();
    loadProducts();
  }, [businessId]);

  useEffect(() => {
    if (!businessId) return;
    const businessName = businesses.find((item) => item.id === businessId)?.name || "this business";
    if (!goal.trim()) {
      setGoal(`Launch a revenue-focused campaign for ${businessName}`);
    }
    if (!contentGoal.trim()) {
      setContentGoal(`Create launch-ready marketing content for ${businessName}`);
    }
  }, [businessId, businesses, goal, contentGoal]);

  // â”€â”€ Auto-scroll agent log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [agentEvents]);

  // â”€â”€ Data loaders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function loadCampaigns() {
    if (!businessId) return [] as MarketingCampaign[];
    setCampaignsLoading(true);
    try {
      const c = await api.listCampaigns(businessId);
      setCampaigns(c);
      return c;
    } catch (e: any) {
      const message = actionErrorMessage(e, "Could not load campaigns from the backend.");
      setError(message);
      toast.error(message);
      return [] as MarketingCampaign[];
    } finally {
      setCampaignsLoading(false);
    }
  }

  async function loadIntegrations() {
    if (!businessId) return;
    setIntegrationsLoading(true);
    setIntegrationLogsLoading(true);
    try {
      const [list, logs] = await Promise.all([
        api.getIntegrations(businessId),
        api.listIntegrationActionLogs(businessId, undefined, 30),
      ]);
      setIntegrations(list);
      setIntegrationLogs(logs as IntegrationActionLog[]);
    } catch (e) { console.error(e); }
    finally {
      setIntegrationsLoading(false);
      setIntegrationLogsLoading(false);
    }
  }

  async function loadIntegrationAccounts() {
    if (!businessId) return;
    setIntegrationAccountsLoading(true);
    try {
      const list = await api.listCredentials(businessId);
      setIntegrationAccounts(
        Object.fromEntries(list.map((item: IntegrationAccount & { provider?: string }) => [item.provider || item.platform, item]))
      );
    } catch (e) {
      console.error(e);
    } finally {
      setIntegrationAccountsLoading(false);
    }
  }

  async function loadAnalytics() {
    if (!businessId) return;
    setAnalyticsLoading(true);
    try {
      const raw = await api.getMarketingAnalytics(businessId);
      const totals = raw.totals || {};
      const data: AnalyticsData & { ai_insights?: string | string[] } = {
        total_impressions: totals.impressions ?? raw.total_impressions ?? 0,
        total_clicks: totals.clicks ?? raw.total_clicks ?? 0,
        total_conversions: totals.conversions ?? raw.total_conversions ?? 0,
        total_spend_cents: raw.total_spend_cents ?? 0,
        total_revenue_usd: totals.revenue_usd ?? raw.total_revenue_usd ?? 0,
        ctr: raw.ctr ?? 0,
        campaigns: (raw.campaigns || []).map((campaign: any) => ({
          id: campaign.id || campaign.campaign_id,
          name: campaign.name || campaign.campaign_name || "Campaign",
          type: campaign.type || campaign.campaign_type || "multi_channel",
          impressions: campaign.impressions || 0,
          clicks: campaign.clicks || 0,
          ctr: campaign.ctr || 0,
          conversions: campaign.conversions || 0,
          spend_cents: campaign.spend_cents || Math.round((campaign.spend_usd || 0) * 100),
          revenue_usd: campaign.revenue_usd || 0,
          analytics_source: campaign.analytics_source || "real",
        })),
        insights: raw.insights,
        ai_insights: raw.ai_insights,
      };
      if (typeof data.ai_insights === "string") {
        data.insights = data.ai_insights.split(/(?<=[.!?])\s+/).filter(Boolean);
      } else if (Array.isArray(data.ai_insights)) {
        data.insights = data.ai_insights;
      }
      setAnalytics(data);
    } catch (e) { console.error(e); }
    finally { setAnalyticsLoading(false); }
  }

  async function loadCalendar() {
    if (!businessId) return;
    setCalendarLoading(true);
    try {
      const posts = await api.getCalendar(businessId);
      setCalendarPosts(posts);
    } catch (e) { console.error(e); }
    finally { setCalendarLoading(false); }
  }

  async function loadContacts() {
    if (!businessId) return;
    setContactsLoading(true);
    try {
      const list = await api.listContacts(businessId);
      setContacts(list as ContactRow[]);
    } catch (e) { console.error(e); }
    finally { setContactsLoading(false); }
  }

  async function handleContactCsv(file?: File | null) {
    if (!businessId || !file) return;
    setImportingContacts(true);
    try {
      const result = await api.importContactsCsv(businessId, file);
      toast.success(`Imported ${result.imported || 0} contacts. ${result.skipped_duplicates || 0} duplicates skipped.`);
      await loadContacts();
    } catch (e: any) {
      toast.error(e.message || "Contact import failed.");
    } finally {
      setImportingContacts(false);
      if (contactFileInputRef.current) contactFileInputRef.current.value = "";
    }
  }

  async function handleCalendarSync() {
    if (!businessId) return;
    setSyncingCalendar(true);
    try {
      const result = await api.syncGoogleCalendar(businessId);
      toast.success(`Google Calendar sync complete: ${result.imported || 0} events imported.`);
      await loadCalendar();
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "Google Calendar sync failed. Reconnect Google with calendar permission, then retry."));
    } finally {
      setSyncingCalendar(false);
    }
  }

  async function loadProducts() {
    if (!businessId) return;
    setProductsLoading(true);
    try {
      const list = await api.listProducts(businessId);
      setProducts(list);
      if (selectedProductId && !list.some((product) => product.id === selectedProductId)) {
        setSelectedProductId("");
      }
    } catch (e) { console.error(e); }
    finally { setProductsLoading(false); }
  }

  const selectedProduct = products.find((product) => product.id === selectedProductId) || null;
  const productContextLine = selectedProduct
    ? ` Focus on product ${selectedProduct.name} priced at ${selectedProduct.price} ${selectedProduct.currency?.toUpperCase()}.`
    : "";

  function campaignBusinessId(campaignId: string): string {
    const campaign = campaigns.find((item) => item.id === campaignId) || (generatedContent?.id === campaignId ? generatedContent : null);
    return String(campaign?.business_id || businessId || "");
  }

  function applyAgenticPlaybook(playbook: typeof AGENTIC_PLAYBOOKS[number]) {
    setGoal(playbook.goal);
    setPlatforms(playbook.platforms);
    setTab("engine");
  }

  // â”€â”€ Engine: run / stop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function stopEngine() {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setRunning(false);
    setBrowserPreview(null);
  }

  function normalizeBrowserEvent(raw: any, platform: string): AgentEvent | null {
    const label = platform === "wordpress" ? "WordPress" : platform.charAt(0).toUpperCase() + platform.slice(1);
    const clean = (value: any) => cleanDisplayText(typeof value === "string" ? value : "");

    if (raw.type === "start") {
      return {
        type: "start",
        agent: "Browser Agent",
        message: `Launching live browser operator for ${label}.`,
        data: raw,
      };
    }

    if (raw.type === "thinking") {
      return {
        type: "thinking",
        agent: "Browser Agent",
        message: clean(raw.thought) || `Working on step ${raw.step ?? 0}`,
        step: raw.step,
        data: raw,
      };
    }

    if (raw.type === "step") {
      const action = clean(raw.action || raw.tool || "Action");
      const result = clean(raw.result);
      return {
        type: "step_complete",
        agent: "Browser Agent",
        message: [action, result].filter(Boolean).join(" - ") || "Browser step completed.",
        step: raw.step,
        data: raw,
      };
    }

    if (raw.type === "blocked") {
      return {
        type: "error",
        agent: "Browser Agent",
        message: clean(raw.reason) || "The browser encountered a blocker and is retrying.",
        step: raw.step,
        data: raw,
      };
    }

    if (raw.type === "result") {
      const status = clean(raw.status || "");
      const summary = clean(raw.text);
      const message = status
        ? `${label} browser result: ${status.replace(/_/g, " ")}${summary ? ` - ${summary}` : ""}`
        : summary || `${label} browser action returned a result.`;
      return {
        type: ["published", "done"].includes(status) ? "complete" : "warning",
        agent: "Browser Agent",
        message,
        data: { ...raw, summary },
      };
    }

    if (raw.type === "error") {
      return {
        type: "error",
        agent: "Browser Agent",
        message: clean(raw.message) || "Browser action failed before a verified result.",
        data: raw,
      };
    }

    return null;
  }

  function updateBrowserPreview(raw: any, platform: string) {
    setBrowserPreview(prev => ({
      platform,
      status: cleanDisplayText(raw.browser_status || raw.status || raw.type || prev?.status || "active"),
      screenshot: raw.screenshot ? `data:image/jpeg;base64,${raw.screenshot}` : prev?.screenshot,
      url: cleanDisplayText(raw.url || prev?.url || ""),
      title: cleanDisplayText(raw.title || prev?.title || ""),
      lastAction: cleanDisplayText(raw.action || raw.tool || raw.thought || prev?.lastAction || ""),
      summary: cleanDisplayText(raw.text || prev?.summary || ""),
      step: raw.step ?? prev?.step,
    }));
  }

  async function confirmBrowserPublish() {
    if (!browserRun?.runId) return;
    setConfirmingPublish(true);
    try {
      await api.controlBrowserRun(browserRun.runId, "confirm_publish");
      toast.info("Final publish confirmation sent to the browser agent.");
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "The browser confirmation could not be sent."));
    } finally {
      setConfirmingPublish(false);
    }
  }

  async function submitEmailSend() {
    if (!emailSendModal) return;
    const recipientEmails = emailSendModal.recipients.split(",").map(item => item.trim()).filter(Boolean);
    if (recipientEmails.length === 0) {
      toast.error("Enter at least one recipient email.");
      return;
    }
    try {
      const targetBusinessId = campaignBusinessId(emailSendModal.campaignId);
      const result = await api.publishCampaign(targetBusinessId, emailSendModal.campaignId, "email", { recipient_emails: recipientEmails });
      if (isRealSuccessStatus(result?.status)) {
        toast.success("Email campaign sent.");
      } else {
        toast.error(cleanDisplayText(result?.message) || `Email send returned status: ${result?.status || "unknown"}.`);
      }
      setEmailSendModal(null);
      await loadCampaigns();
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "Email send failed. No sent status was recorded."));
    }
  }

  function buildPublishDetailsModal(campaignId: string, platform: string): PublishDetailsModalState | null {
    const campaign = campaigns.find((item) => item.id === campaignId) || (generatedContent?.id === campaignId ? generatedContent : null);
    const imageUrl = campaign?.image_url || campaign?.content?.image_url || "";
    if (platform === "facebook") {
      return {
        campaignId,
        platform,
        title: "Publish to Facebook Page",
        fields: [{ key: "page_id", label: "Facebook Page ID", placeholder: "Enter the Page ID to publish to", required: true }],
        values: { page_id: "" },
      };
    }
    if (platform === "instagram") {
      return {
        campaignId,
        platform,
        title: "Publish to Instagram",
        fields: [
          { key: "account_id", label: "Instagram Account ID", placeholder: "Professional Instagram account ID", required: true },
          { key: "media_url", label: "Public Image URL", placeholder: "https://... image URL required by Instagram Graph", required: true },
        ],
        values: { account_id: "", media_url: imageUrl },
      };
    }
    if (platform === "slack") {
      return {
        campaignId,
        platform,
        title: "Send to Slack",
        fields: [{ key: "channel", label: "Slack Channel", placeholder: "Channel ID, e.g. C012ABCDEF", required: true }],
        values: { channel: "" },
      };
    }
    if (platform === "notion") {
      return {
        campaignId,
        platform,
        title: "Create Notion Page",
        fields: [{ key: "parent_page_id", label: "Parent Page ID", placeholder: "Notion parent page ID", required: true }],
        values: { parent_page_id: "" },
      };
    }
    if (platform === "wordpress") {
      return {
        campaignId,
        platform,
        title: "Create WordPress Draft",
        fields: [{ key: "site_id", label: "WordPress Site ID", placeholder: "WordPress.com site ID", required: true }],
        values: { site_id: "" },
      };
    }
    return null;
  }

  async function submitPublishDetails() {
    if (!publishDetailsModal) return;
    const missing = publishDetailsModal.fields.find((field) => field.required && !publishDetailsModal.values[field.key]?.trim());
    if (missing) {
      toast.error(`Enter ${missing.label}.`);
      return;
    }
    const payload = Object.fromEntries(
      Object.entries(publishDetailsModal.values).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])
    );
    await publishOfficial(publishDetailsModal.campaignId, publishDetailsModal.platform, payload);
    setPublishDetailsModal(null);
  }

  async function submitSchedule() {
    if (!scheduleModal) return;
    try {
      const targetBusinessId = campaignBusinessId(scheduleModal.campaignId);
      await api.scheduleCampaign(
        targetBusinessId,
        scheduleModal.campaignId,
        scheduleModal.scheduledAt,
        Intl.DateTimeFormat().resolvedOptions().timeZone,
        scheduleModal.platform
      );
      setCampaigns(prev => prev.map(c => c.id === scheduleModal.campaignId ? { ...c, status: "scheduled", lifecycle_status: "scheduled", scheduled_at: scheduleModal.scheduledAt } : c));
      setScheduleModal(null);
      toast.success("Campaign scheduled.");
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "Campaign scheduling failed. No schedule was saved."));
    }
  }

  async function submitReject() {
    if (!rejectModal || !rejectModal.reason.trim()) {
      toast.error("Enter a rejection reason.");
      return;
    }
    try {
      await api.rejectCampaign(campaignBusinessId(rejectModal.campaignId), rejectModal.campaignId, rejectModal.reason.trim());
      setRejectModal(null);
      await loadCampaigns();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function runEngine() {
    if (!businessId || !goal.trim() || running) return;
    setRunning(true);
    setAgentEvents([]);
    setBrowserPreview(null);
    setError(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) { setError("Not authenticated"); setRunning(false); return; }
    const params = new URLSearchParams({
      goal: `${goal.trim()}${productContextLine}`.trim(),
      budget_usd: budget,
      platforms: platforms.join(","),
      token,
    });
    const es = new EventSource(`${API_URL}/marketing/${businessId}/run?${params}`);
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const evt: AgentEvent = JSON.parse(e.data);
        setAgentEvents(prev => [...prev, { ...evt, message: cleanDisplayText(evt.message) }]);
        if (evt.type === "complete" || evt.type === "error") {
          setRunning(false);
          es.close();
          esRef.current = null;
          if (evt.type === "complete") {
            const ids = Array.isArray(evt.data?.campaign_ids) ? evt.data.campaign_ids : [];
            loadCampaigns().then((fresh) => {
              const createdId = ids.find((id: string) => fresh.some((campaign) => campaign.id === id)) || fresh[0]?.id;
              if (createdId) setExpanded(createdId);
            });
          }
          if (evt.type === "error") setError(evt.message);
        }
      } catch { /* ignore parse errors */ }
    };
    es.onerror = () => { setRunning(false); es.close(); esRef.current = null; };
  }

  // â”€â”€ Publish campaign â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function publishOfficial(campaignId: string, platform: string, payload?: Record<string, unknown>) {
    setPublishing(campaignId + ":" + platform);
    try {
      const targetBusinessId = campaignBusinessId(campaignId);
      const result = await api.publishCampaign(targetBusinessId, campaignId, platform, payload);
      if (isRealSuccessStatus(result?.status)) {
        const fallbackNote = result?.fallback_from === "sendgrid" ? " SendGrid rejected the send, so Gmail OAuth was used." : "";
        toast.success((cleanDisplayText(result?.message) || `${platform} publish verified.`) + fallbackNote);
      } else if (result?.status === "draft_ready") {
        toast.info(cleanDisplayText(result?.message) || `${platform} draft was created. It has not been launched or published.`);
      } else {
        toast.error(cleanDisplayText(result?.message) || `${platform} returned status: ${result?.status || "unknown"}.`);
      }
      await loadCampaigns();
    } catch (e: any) {
      toast.error(actionErrorMessage(e, `${platform} publish failed. No publish status was recorded.`));
    } finally {
      setPublishing(null);
    }
  }

  async function handlePublish(campaignId: string, platform: string) {
    const useBrowserMode = platform.endsWith("_browser");
    const targetPlatform = useBrowserMode ? platform.replace(/_browser$/, "") : platform;
    let keepPublishingState = false;
    setPublishing(campaignId + ":" + targetPlatform);
    try {
      if (targetPlatform === "email" && !useBrowserMode) {
        setPublishing(null);
        setEmailSendModal({ campaignId, recipients: "" });
        return;
      }

      if (targetPlatform === "google_ads" || targetPlatform === "meta_ads") {
        setPublishing(null);
        await publishOfficial(campaignId, targetPlatform);
        return;
      }

      const details = useBrowserMode ? null : buildPublishDetailsModal(campaignId, targetPlatform);
      if (details) {
        setPublishing(null);
        setPublishDetailsModal(details);
        return;
      }

      if (!useBrowserMode && ["linkedin", "twitter"].includes(targetPlatform)) {
        await publishOfficial(campaignId, targetPlatform);
        return;
      }

      if (!BROWSER_PUBLISH_PLATFORMS.has(targetPlatform)) {
        await publishOfficial(campaignId, targetPlatform);
        return;
      }

      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
      if (!token) {
        toast.error("You need to sign in again before publishing.");
        return;
      }

      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      setTab("engine");
      setGoal(`Publish ${targetPlatform} campaign`);
      setRunning(true);
      setError(null);
      setAgentEvents([]);
      setBrowserPreview({
        platform: targetPlatform,
        status: "launching",
        lastAction: "Preparing live browser session",
      });
      keepPublishingState = true;

      const params = new URLSearchParams({ token });
      const streamUrl = `${API_URL}/marketing/${campaignBusinessId(campaignId)}/campaigns/${campaignId}/browser-stream/${targetPlatform}?${params}`;
      const es = new EventSource(streamUrl);
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          const raw = JSON.parse(e.data);
          if (raw.type === "start" && raw.run_id) {
            setBrowserRun({ runId: raw.run_id, campaignId, platform: targetPlatform, awaitingConfirmation: false });
          }
          updateBrowserPreview(raw, targetPlatform);
          const normalized = normalizeBrowserEvent(raw, targetPlatform);
          if (normalized) {
            setAgentEvents(prev => [...prev, normalized]);
          }

          if (raw.type === "status" && ["awaiting_final_confirmation", "awaiting_user_approval"].includes(raw.status) && raw.run_id) {
            setBrowserRun({ runId: raw.run_id, campaignId, platform: targetPlatform, awaitingConfirmation: true });
            setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "awaiting_final_confirmation", lifecycle_status: "awaiting_final_confirmation" } : c));
            toast.info(`The ${targetPlatform} draft is ready. Review it and confirm the final publish step when you're ready.`);
          }

          if (raw.type === "done") {
            setRunning(false);
            es.close();
            esRef.current = null;
            setPublishing(null);
            if (raw.status === "published") {
              toast.success(`Browser automation verified the ${targetPlatform} publish.`);
              setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "published", lifecycle_status: "published" } : c));
              setBrowserRun(null);
            } else if (raw.status === "done") {
              toast.info(`${targetPlatform} browser run finished without publish verification. Campaign remains approved.`);
              setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "approved", lifecycle_status: "approved" } : c));
              setBrowserRun(null);
            } else if (raw.status === "waiting_for_manual_login") {
              toast.info(`${targetPlatform} is waiting for login in the live browser. Complete login there and this run will continue.`);
            } else if (raw.status === "needs_login") {
              toast.error(`${targetPlatform} still needs login or verification. Complete it in the browser, then retry.`);
              setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "approved", lifecycle_status: "approved" } : c));
              setBrowserRun(null);
            } else if (raw.status === "composer_not_found") {
              toast.error(`${targetPlatform} composer was not found. Nothing was published.`);
              setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "approved", lifecycle_status: "approved" } : c));
              setBrowserRun(null);
            } else if (raw.status === "publish_unconfirmed" || raw.status === "awaiting_user_approval" || raw.status === "image_required") {
              toast.info(`${targetPlatform} did not publish. Status: ${cleanDisplayText(raw.status)}.`);
              setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, status: "approved", lifecycle_status: "approved" } : c));
              setBrowserRun(null);
            } else {
              toast.error(`The ${targetPlatform} browser action failed. Nothing was published.`);
              setBrowserRun(null);
            }
            loadCampaigns();
          }
        } catch {
          setError("Could not read browser publish event stream.");
        }
      };

      es.onerror = () => {
        setRunning(false);
        es.close();
        esRef.current = null;
        setPublishing(null);
        toast.error(`The ${targetPlatform} browser stream stopped before a verified result.`);
      };
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "Publish action failed. No publish status was recorded."));
    } finally {
      if (!keepPublishingState) {
        setPublishing(null);
      }
    }
  }

  // â”€â”€ Schedule campaign â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function handleSchedule(campaignId: string, platform: string) {
    setScheduleModal({
      campaignId,
      platform,
      scheduledAt: new Date(Date.now() + 3600_000).toISOString().slice(0, 16),
    });
  }

  // â”€â”€ Generate image â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function handleGenerateImage(campaignId: string) {
    setGeneratingImage(campaignId);
    try {
      const result = await api.generateCampaignImage(campaignBusinessId(campaignId), campaignId);
      setCardImages(prev => ({ ...prev, [campaignId]: result.image_url }));
      toast.success("Campaign image is ready.");
    } catch (e: any) {
      toast.error(actionErrorMessage(e, "Image generation failed. Configure a real image provider before retrying."));
    } finally {
      setGeneratingImage(null);
    }
  }

  // â”€â”€ Approve / Reject â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function handleApprove(campaignId: string) {
    setApproving(campaignId);
    try {
      const approved = await api.approveCampaign(campaignBusinessId(campaignId), campaignId);
      setError(null);
      setCampaigns(prev => prev.map(c => c.id === campaignId ? { ...c, ...approved, status: "approved", lifecycle_status: "approved" } : c));
      toast.success("Campaign approved. Publishing actions are now unlocked.");
      await loadCampaigns();
    } catch (e: any) {
      const message = actionErrorMessage(e, "Campaign approval failed. Refresh campaigns and try again.");
      setError(message);
      toast.error(message);
    }
    finally { setApproving(null); }
  }

  async function handleReject(campaignId: string) {
    setRejectModal({ campaignId, reason: "" });
  }

  // â”€â”€ Content Studio generate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function handleGenerateContent() {
    if (!businessId || !contentGoal.trim()) return;
    setGeneratingContent(true);
    setGeneratedContent(null);
    try {
      const result = await api.generateContentStudioAsset(businessId, {
        content_type: contentType,
        tone,
        audience: audience || currentBusinessName,
        cta,
        goal: `${contentGoal}${productContextLine}`.trim(),
        product_id: selectedProductId || undefined,
      });
      setGeneratedContent(result);
      await loadCampaigns();
    } catch (e: any) { setError(e.message); }
    finally { setGeneratingContent(false); }
  }

  // â”€â”€ Integrations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function handleConnect(platform: string) {
    try {
      const oauthProvider = INTEGRATION_PLATFORMS.find((item) => item.id === platform)?.oauthProvider || platform;
      const result = await api.connectIntegration(businessId, oauthProvider);
      if (result.type === "provider_config_missing") {
        toast.error(result.message || `${platform} OAuth is not configured by the app owner yet.`);
        return;
      }
      const authorizationUrl = result.authorization_url || result.auth_url;
      if (authorizationUrl) {
        window.location.assign(authorizationUrl);
        return;
      } else {
        toast.info(result.message || `OAuth connection is not available for ${platform}.`);
      }
    } catch (e: any) { toast.error("Connect failed: " + (e.message || "Unknown error")); }
  }

  async function handleDisconnect(platform: string) {
    try {
      await api.disconnectIntegration(businessId, platform);
      await loadIntegrations();
    } catch (e: any) { toast.error("Disconnect failed: " + (e.message || "Unknown error")); }
  }

  async function handleTestOAuth(platform: string) {
    setTestingOAuth(platform);
    try {
      const result = await api.testOAuthIntegration(businessId, platform);
      toast.success(result.message || `${platform} connection is healthy.`);
      await loadIntegrations();
    } catch (e: any) {
      toast.error("Test failed: " + (e.message || "Unknown error"));
    } finally {
      setTestingOAuth(null);
    }
  }

  async function handleRefreshOAuth(platform: string) {
    setRefreshingOAuth(platform);
    try {
      const result = await api.refreshIntegration(businessId, platform);
      toast.success(result.message || `${platform} token refresh checked.`);
      await loadIntegrations();
    } catch (e: any) {
      toast.error("Refresh failed: " + (e.message || "Unknown error"));
    } finally {
      setRefreshingOAuth(null);
    }
  }

  async function handleProviderToolTest(platform: string) {
    try {
      if (platform === "gmail" || platform === "sendgrid") {
        const recipient = window.prompt(`Send a ${platform === "gmail" ? "Gmail" : "SendGrid"} test email to:`);
        if (!recipient) return;
        const payload = {
          to: [recipient],
          subject: "AI Business Builder integration test",
          text: `This is a real ${platform === "gmail" ? "Gmail OAuth" : "SendGrid"} test from AI Business Builder.`,
          html: `<p>This is a real <strong>${platform === "gmail" ? "Gmail OAuth" : "SendGrid"}</strong> test from AI Business Builder.</p>`,
          from_name: currentBusinessName || "AI Business Builder",
        };
        const result = platform === "gmail"
          ? await api.sendGmailTool(businessId, payload)
          : await api.sendSendGridTool(businessId, payload);
        toast.success(result.message || `${platform === "gmail" ? "Gmail" : "SendGrid"} test email sent.`);
      } else if (platform === "notion") {
        const parentPageId = window.prompt("Notion parent page ID for the test page:");
        if (!parentPageId) return;
        const result = await api.createNotionPageTool(businessId, {
          parent_page_id: parentPageId,
          title: "AI Business Builder integration test",
          content: `Created from AI Business Builder for ${currentBusinessName || "your business"}.`,
        });
        toast.success(result.message || "Notion test page created.");
      }
      await loadIntegrations();
    } catch (e: any) {
      toast.error("Integration action failed: " + (e.message || "Unknown error"));
    }
  }

  async function handleSaveApiKey(platform: string) {
    const key = apiKeys[platform];
    if (!key) return;
    setSavingKey(platform);
    try {
      await api.connectWithApiKey(businessId, platform, key);
      await loadIntegrations();
      setApiKeys(prev => ({ ...prev, [platform]: "" }));
    } catch (e: any) { toast.error("Save failed: " + (e.message || "Unknown error")); }
    finally { setSavingKey(null); }
  }

  function openAccountModal(platform: string) {
    const vault = ACCOUNT_VAULT_PLATFORMS.find((item) => item.id === platform);
    const existing = getIntegrationAccount(platform);
    setAccountModal({
      platform,
      label: vault?.label || platform,
      email: "",
      phone: "",
      password: "",
      status: existing?.status || "disconnected",
      identifierPreview: existing?.identifier_preview || "",
      lastTestedAt: existing?.last_tested_at,
      lastError: existing?.last_error,
    });
  }

  async function saveAccountCredentials() {
    if (!accountModal || !businessId) return;
    if (!accountModal.email.trim() && !accountModal.phone.trim()) {
      toast.error("Enter an email/username or a phone number for the account.");
      return;
    }
    if (!accountModal.password.trim()) {
      toast.error("Enter the account password.");
      return;
    }
    setSavingAccount(accountModal.platform);
    try {
      const saved = await api.saveCredential(accountModal.platform, {
        business_id: businessId,
        login_email: accountModal.email.trim() || undefined,
        phone: accountModal.phone.trim() || undefined,
        password: accountModal.password.trim(),
      });
      const savedPlatform = saved.provider || saved.platform;
      setIntegrationAccounts((prev) => ({ ...prev, [savedPlatform]: saved }));
      setAccountModal((current) =>
        current && current.platform === savedPlatform
          ? {
              ...current,
              status: saved.status,
              identifierPreview: saved.identifier_preview,
              lastTestedAt: saved.last_tested_at,
              lastError: saved.last_error,
              password: "",
            }
          : current
      );
      toast.success("Saved encrypted browser account credentials.");
    } catch (e: any) {
      toast.error("Could not save account credentials: " + (e.message || "Unknown error"));
    } finally {
      setSavingAccount(null);
    }
  }

  async function testSavedAccount(platform: string) {
    if (!businessId) return;
    setTestingAccount(platform);
    try {
      const tested = await api.testCredentialLogin(platform, businessId);
      const testedPlatform = tested.provider || tested.platform;
      setIntegrationAccounts((prev) => ({ ...prev, [testedPlatform]: tested }));
      setAccountModal((current) =>
        current && current.platform === testedPlatform
          ? {
              ...current,
              status: tested.status,
              identifierPreview: tested.identifier_preview,
              lastTestedAt: tested.last_tested_at,
              lastError: tested.last_error,
            }
          : current
      );
      toast.success(tested.status === "connected" ? "Account test passed." : "Account test completed with warnings.");
    } catch (e: any) {
      toast.error("Could not test the saved account: " + (e.message || "Unknown error"));
    } finally {
      setTestingAccount(null);
    }
  }

  async function deleteSavedAccount(platform: string) {
    if (!businessId) return;
    setDeletingAccount(platform);
    try {
      await api.deleteCredential(platform, businessId);
      setIntegrationAccounts((prev) => ({
        ...prev,
        [platform]: {
          id: null,
          platform,
          status: "disconnected",
          identifier_preview: "",
          last_active_at: null,
          last_tested_at: null,
          last_error: null,
        },
      }));
      if (accountModal?.platform === platform) {
        setAccountModal(null);
      }
      toast.success("Saved account removed.");
    } catch (e: any) {
      toast.error("Could not remove the saved account: " + (e.message || "Unknown error"));
    } finally {
      setDeletingAccount(null);
    }
  }

  // â”€â”€ Brand settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function openBrandPanel() {
    setBrandPanelOpen(true);
    try {
      const data = await api.getBrandSystem(businessId);
      if (data) {
        setBrand({
          primary_color:   data.primary_color   || "#6366f1",
          secondary_color: data.secondary_color || "#8b5cf6",
          tone_of_voice:   data.tone_of_voice   || "professional",
          target_audience: data.target_audience || "",
          industry:        data.industry        || "",
          competitors:     Array.isArray(data.competitors) ? data.competitors : [],
          website_url:     data.website_url     || "",
          logo_description:data.logo_description|| "",
        });
        setCompetitorsInput(Array.isArray(data.competitors) ? data.competitors.join(", ") : "");
      }
    } catch { /* brand may not exist yet */ }
  }

  async function saveBrand() {
    setSavingBrand(true);
    try {
      await api.saveBrandSystem(businessId, {
        ...brand,
        competitors: competitorsInput.split(",").map(s => s.trim()).filter(Boolean),
      });
      setBrandSaved(true);
      setTimeout(() => setBrandSaved(false), 2500);
    } catch (e: any) { toast.error("Save failed: " + (e.message || "Unknown error")); }
    finally { setSavingBrand(false); }
  }

  // â”€â”€ Integration status helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function getIntegration(platform: string): IntegrationStatus | undefined {
    return integrations.find(i => i.platform === platform);
  }

  function getIntegrationAccount(platform: string): IntegrationAccount | undefined {
    return integrationAccounts[platform];
  }

  // â”€â”€ Shared styles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const inputStyle: React.CSSProperties = {
    width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0",
    background: "#f8fafc", padding: "9px 12px", fontSize: 13,
    color: "#0f172a", outline: "none", fontFamily: "inherit", boxSizing: "border-box",
  };
  const darkInputStyle: React.CSSProperties = {
    ...inputStyle, background: "rgba(255,255,255,0.06)", border: "1.5px solid rgba(255,255,255,0.12)",
    color: "rgba(255,255,255,0.85)",
  };
  const btnPrimary: React.CSSProperties = {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
    background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff",
    fontWeight: 700, fontSize: 13, padding: "10px 16px", borderRadius: 10,
    border: "none", cursor: "pointer", fontFamily: "inherit",
  };
  const btnSecondary: React.CSSProperties = {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
    background: "#f1f5f9", color: "#374151", fontWeight: 600, fontSize: 12,
    padding: "7px 12px", borderRadius: 8, border: "1px solid #e2e8f0",
    cursor: "pointer", fontFamily: "inherit",
  };
  const btnDanger: React.CSSProperties = {
    ...btnSecondary, background: "#fff", color: "#dc2626", border: "1.5px solid #fecaca",
  };
  const btnGreen: React.CSSProperties = {
    ...btnPrimary, background: "#16a34a",
  };

  const pending = campaigns.filter(c => effectiveCampaignStatus(c) === "pending_approval").length;
  const integrationRank = (platformId: string) => {
    const integration = getIntegration(platformId);
    const isReadySendGrid = platformId === "sendgrid" && integration?.ready_to_connect !== false;
    if (integration?.status === "connected" || isReadySendGrid) return 0;
    if (integration?.ready_to_connect !== false) return 1;
    return 2;
  };
  const integrationGroupLabel = (platformId: string) => {
    const rank = integrationRank(platformId);
    if (rank === 0) return "Connected and ready";
    if (rank === 1) return "Ready to connect";
    return "Not configured yet";
  };
  const sortedIntegrationPlatforms = [...INTEGRATION_PLATFORMS].sort((a, b) => {
    const rank = integrationRank(a.id) - integrationRank(b.id);
    return rank || a.label.localeCompare(b.label);
  });

  // â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", height: "100%", background: "#0f172a", fontFamily: "inherit" }}>

      {/* â”€â”€ Top Bar â”€â”€ */}
      <div style={{ background: "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(15,23,42,0.94))", padding: isMobile ? "14px 18px" : "14px 22px", display: "flex", alignItems: isMobile ? "stretch" : "center", gap: 12, minHeight: 64, flexShrink: 0, zIndex: 10, flexWrap: "wrap", boxShadow: "0 16px 44px rgba(2,6,23,0.24)" }}>
        {/* Logo + title */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginRight: 8, flexShrink: 0 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Bot size={16} color="#fff" />
          </div>
          <span style={{ fontSize: 15, fontWeight: 800, color: "rgba(255,255,255,0.96)" }}>Mission Control</span>
        </div>

        {/* Business selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: isMobile ? "1 1 100%" : "0 1 auto", minWidth: isMobile ? "100%" : 180 }}>
          <select
            value={businessId}
            onChange={e => setBusinessId(e.target.value)}
            style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, padding: "8px 12px", fontSize: 13, color: "rgba(255,255,255,0.92)", outline: "none", fontFamily: "inherit", cursor: "pointer", width: isMobile ? "100%" : 190 }}
          >
            {businesses.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </div>

        {/* Tab navigation */}
        <div style={{ display: "flex", gap: 6, flex: "1 1 420px", overflowX: "auto", paddingBottom: 2 }}>
          {([
            { id: "engine",         label: "Engine",        icon: <Zap size={13} /> },
            { id: "campaigns",      label: "Campaigns",     icon: <Target size={13} /> },
            { id: "content-studio", label: "Content Studio",icon: <Sparkles size={13} /> },
            { id: "analytics",      label: "Analytics",     icon: <BarChart3 size={13} /> },
            { id: "integrations",   label: "Integrations",  icon: <LinkIcon size={13} /> },
            { id: "calendar",       label: "Calendar",      icon: <Calendar size={13} /> },
          ] as const).map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                position: "relative", display: "flex", alignItems: "center", gap: 5,
                padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                border: "none", cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap",
                background: tab === t.id ? "rgba(99,102,241,0.22)" : "transparent",
                color: tab === t.id ? "#a5b4fc" : "rgba(255,255,255,0.56)",
              }}
            >
              {t.icon} {t.label}
              {t.id === "campaigns" && pending > 0 && (
                <span style={{ position: "absolute", top: 2, right: 2, width: 16, height: 16, borderRadius: "50%", background: "#f59e0b", color: "#fff", fontSize: 9, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>{pending}</span>
              )}
            </button>
          ))}
        </div>

        {/* Brand Settings button */}
        <button
          onClick={openBrandPanel}
          style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, padding: "8px 14px", fontSize: 12, fontWeight: 700, color: "#e2e8f0", cursor: "pointer", fontFamily: "inherit", flexShrink: 0, marginLeft: isMobile ? 0 : "auto" }}
        >
          <Settings size={13} /> Brand Settings
        </button>
      </div>

      {/* â”€â”€ Error banner â”€â”€ */}
      {error && (
        <div style={{ display: "flex", gap: 8, background: "#fef2f2", borderTop: "1px solid #fecaca", borderBottom: "1px solid #fecaca", padding: "10px 24px", fontSize: 13, color: "#dc2626", alignItems: "center", flexShrink: 0 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0 }} />
          {cleanDisplayText(error)}
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#dc2626", fontSize: 16, lineHeight: 1 }}>x</button>
        </div>
      )}

      {/* â”€â”€ Job progress â”€â”€ */}
      {jobId && (
        <div style={{ padding: "8px 24px", flexShrink: 0 }}>
          <JobProgress jobId={jobId} onComplete={() => { setJobId(null); loadCampaigns(); }} onError={msg => setError(msg)} />
        </div>
      )}

      {/* â”€â”€ Main content area â”€â”€ */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", minHeight: 0 }}>

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            ENGINE TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "engine" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isMobile ? "1fr" : `${isCompactDesktop ? 300 : 320}px minmax(0, 1fr)`,
              gridTemplateRows: isMobile ? "auto auto" : "minmax(0, 1fr)",
              width: "100%",
              height: "100%",
              overflow: isMobile ? "auto" : "hidden",
            }}
          >

            {/* Left panel */}
            <div className="marketing-scroll" style={{ gridColumn: isMobile ? "1 / -1" : "1 / 2", gridRow: isMobile ? "1 / 2" : "1 / 2", width: "100%", background: "#0f172a", borderRight: isMobile ? "none" : "1px solid rgba(255,255,255,0.08)", borderBottom: isMobile ? "1px solid rgba(255,255,255,0.08)" : "none", overflowY: isMobile ? "visible" : "auto", padding: 20, display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
              {/* Goal */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Campaign Goal</label>
                <textarea
                  value={goal}
                  onChange={e => setGoal(e.target.value)}
                  rows={3}
                  placeholder="e.g. Increase sales by 20%, launch new product..."
                  style={{ ...darkInputStyle, resize: "none", width: "100%", boxSizing: "border-box" }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Featured Product</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  style={{ ...darkInputStyle, width: "100%", boxSizing: "border-box" }}
                  disabled={productsLoading}
                >
                  <option value="">No specific product</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name} ({product.price} {product.currency?.toUpperCase()})
                    </option>
                  ))}
                </select>
                {selectedProduct ? (
                  <p style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", margin: "8px 0 0", lineHeight: 1.5 }}>
                    Campaign execution will stay anchored to {selectedProduct.name} and carry that context into generated content.
                  </p>
                ) : null}
              </div>

              {/* Budget */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Budget (USD)</label>
                <input type="number" min="10" value={budget} onChange={e => setBudget(e.target.value)} style={{ ...darkInputStyle, width: "100%", boxSizing: "border-box" }} />
              </div>

              {/* Platform chips */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Platforms</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {PLATFORM_CHIPS.map(({ id, label }) => {
                    const active = platforms.includes(id);
                    return (
                      <button
                        key={id}
                        onClick={() => setPlatforms(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
                        style={{ padding: "5px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600, border: `1.5px solid ${active ? "#818cf8" : "rgba(255,255,255,0.12)"}`, background: active ? "rgba(99,102,241,0.25)" : "rgba(255,255,255,0.05)", color: active ? "#a5b4fc" : "rgba(255,255,255,0.4)", cursor: "pointer", fontFamily: "inherit" }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quick goals */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Quick Goals</label>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {QUICK_GOALS.map(g => (
                    <button
                      key={g}
                      onClick={() => setGoal(g)}
                      style={{ textAlign: "left", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "8px 10px", fontSize: 12, color: "rgba(255,255,255,0.6)", cursor: "pointer", fontFamily: "inherit" }}
                    >
                      {truncateClean(g, 72)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 8 }}>Agentic Playbooks</label>
                <div style={{ display: "grid", gap: 8 }}>
                  {AGENTIC_PLAYBOOKS.map((playbook) => (
                    <button
                      key={playbook.label}
                      onClick={() => applyAgenticPlaybook(playbook)}
                      style={{
                        textAlign: "left",
                        background: "linear-gradient(135deg, rgba(34,197,94,0.13), rgba(99,102,241,0.09))",
                        border: "1px solid rgba(34,197,94,0.24)",
                        borderRadius: 12,
                        padding: "10px 12px",
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      <span style={{ display: "block", color: "#bbf7d0", fontSize: 12, fontWeight: 900 }}>{playbook.label}</span>
                      <span style={{ display: "block", color: "rgba(255,255,255,0.52)", fontSize: 11, lineHeight: 1.45, marginTop: 4 }}>
                        {playbook.platforms.join(" -> ")}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Run button */}
              <button
                onClick={running ? stopEngine : runEngine}
                disabled={!running && (!goal.trim() || !businessId)}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  background: running ? "#dc2626" : "linear-gradient(135deg,#6366f1,#8b5cf6)",
                  color: "#fff", border: "none", borderRadius: 12, padding: "13px",
                  fontSize: 14, fontWeight: 800, cursor: (!running && (!goal.trim() || !businessId)) ? "not-allowed" : "pointer",
                  fontFamily: "inherit", opacity: (!running && (!goal.trim() || !businessId)) ? 0.5 : 1,
                }}
              >
                {running ? <><Square size={15} /> Stop Engine</> : <><Play size={15} /> Run AI Campaign</>}
              </button>
              <NextLink
                href="/marketing/generated-content"
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  background: "rgba(255,255,255,0.05)",
                  color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 12, padding: "12px 14px",
                  fontSize: 13, fontWeight: 700, textDecoration: "none",
                }}
              >
                <Sparkles size={14} />
                View Generated Content
              </NextLink>
            </div>

            {/* Centre panel â€” live log */}
            <div style={{ gridColumn: isMobile ? "1 / -1" : "2 / 3", gridRow: isMobile ? "2 / 3" : "1 / 2", minHeight: isMobile ? 420 : 0, background: "#0f172a", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "12px 20px", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: running ? "#10b981" : "rgba(255,255,255,0.2)", boxShadow: running ? "0 0 8px #10b981" : "none" }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(255,255,255,0.7)" }}>
                  {running ? "AI agents executing..." : agentEvents.length > 0 ? "Execution complete" : "Ready to run"}
                </span>
                {agentEvents.length > 0 && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginLeft: "auto" }}>{agentEvents.length} events</span>}
              </div>

              <div ref={logRef} className="marketing-scroll marketing-scroll--soft" style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
                {browserPreview && (
                  <div style={{ background: "rgba(15,23,42,0.9)", border: "1px solid rgba(99,102,241,0.28)", borderRadius: 14, padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                      <div>
                        <p style={{ fontSize: 11, fontWeight: 700, color: "#818cf8", textTransform: "uppercase", letterSpacing: "0.08em", margin: 0 }}>Live Browser Preview</p>
                        <p style={{ fontSize: 13, color: "rgba(255,255,255,0.9)", margin: "4px 0 0" }}>
                          {cleanDisplayText(browserPreview.title) || "Launching browser session"}
                        </p>
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#cbd5f5" }}>
                        {cleanDisplayText(browserPreview.status)}
                      </span>
                    </div>
                    {browserPreview.screenshot && (
                      <img
                        src={browserPreview.screenshot}
                        alt="Live browser screenshot"
                        style={{ width: "100%", borderRadius: 12, border: "1px solid rgba(255,255,255,0.08)", objectFit: "cover" }}
                      />
                    )}
                    <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1.2fr 0.8fr", gap: 10 }}>
                      <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "10px 12px" }}>
                        <p style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.35)", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Current URL</p>
                        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.78)", margin: 0, wordBreak: "break-word" }}>{cleanDisplayText(browserPreview.url) || "Connecting..."}</p>
                      </div>
                      <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "10px 12px" }}>
                        <p style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.35)", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Last Action</p>
                        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.78)", margin: 0 }}>{cleanDisplayText(browserPreview.lastAction) || "Waiting for next action"}</p>
                      </div>
                    </div>
                    {browserPreview.summary && (
                      <div style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.24)", borderRadius: 10, padding: "10px 12px" }}>
                        <p style={{ fontSize: 10, fontWeight: 700, color: "#6ee7b7", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Latest Summary</p>
                        <p style={{ fontSize: 12, color: "#d1fae5", margin: 0, whiteSpace: "pre-wrap" }}>{cleanDisplayText(browserPreview.summary)}</p>
                      </div>
                    )}
                    {browserRun?.awaitingConfirmation && (
                      <div style={{ background: "rgba(59,130,246,0.12)", border: "1px solid rgba(59,130,246,0.28)", borderRadius: 12, padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                        <div>
                          <p style={{ fontSize: 11, fontWeight: 700, color: "#93c5fd", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Final confirmation required</p>
                          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.78)", margin: 0 }}>The browser agent stopped at the last publish step. Review the draft, then confirm when you want it to click the final publish button.</p>
                        </div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button onClick={confirmBrowserPublish} disabled={confirmingPublish} style={{ ...btnPrimary, padding: "8px 14px", fontSize: 12 }}>
                            {confirmingPublish ? <Loader2 size={12} /> : <Send size={12} />} Confirm and Publish
                          </button>
                          <button onClick={() => setBrowserRun(null)} style={{ ...btnSecondary, padding: "8px 14px", fontSize: 12 }}>
                            Keep Draft Open
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {agentEvents.length === 0 && !running && (
                  <div style={{ maxWidth: 820, margin: "0 auto", width: "100%", display: "flex", flexDirection: "column", gap: 18, padding: "56px 8px 20px" }}>
                    <div style={{ borderRadius: 24, border: "1px solid rgba(99,102,241,0.18)", background: "linear-gradient(135deg, rgba(99,102,241,0.16), rgba(15,23,42,0.82))", padding: isMobile ? 22 : 28, boxShadow: "0 24px 60px rgba(2,6,23,0.24)" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 18 }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0, flex: "1 1 420px" }}>
                          <div style={{ width: 56, height: 56, borderRadius: 18, background: "rgba(99,102,241,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Bot size={28} color="#a5b4fc" />
                          </div>
                          <div>
                            <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 800, color: "rgba(255,255,255,0.45)", textTransform: "uppercase", letterSpacing: "0.12em" }}>AI Marketing Mission Control</p>
                            <h3 style={{ margin: 0, fontSize: 24, lineHeight: 1.1, color: "#fff", letterSpacing: "-0.03em" }}>Launch campaigns, review generated assets, and publish from one live workspace.</h3>
                          </div>
                          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.68)" }}>
                            Set a campaign goal on the left, run the engine, then move into the dedicated content workspace to polish and publish the generated assets.
                          </p>
                          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3, minmax(0, 1fr))", gap: 10, marginTop: 4 }}>
                            {[
                              ["Best wedge", "Local home services"],
                              ["First outcome", "Booked calls, not vanity metrics"],
                              ["Proof loop", "Generate, approve, publish, measure"],
                            ].map(([label, value]) => (
                              <div key={label} style={{ borderRadius: 14, border: "1px solid rgba(45,212,191,0.18)", background: "rgba(8,47,73,0.26)", padding: "10px 12px" }}>
                                <p style={{ margin: "0 0 5px", color: "#67e8f9", fontSize: 10, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</p>
                                <p style={{ margin: 0, color: "#e0f2fe", fontSize: 12, lineHeight: 1.45, fontWeight: 800 }}>{value}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(120px, 1fr))", gap: 12, minWidth: isMobile ? "100%" : 280 }}>
                          {[
                            { label: "Campaigns", value: campaigns.length, tone: "#a5b4fc" },
                            { label: "Pending review", value: pending, tone: "#fbbf24" },
                            { label: "Connected platforms", value: integrations.filter((item) => item.status === "connected").length, tone: "#34d399" },
                            { label: "Saved accounts", value: Object.values(integrationAccounts).filter((item) => item?.id).length, tone: "#93c5fd" },
                          ].map((item) => (
                            <div key={item.label} style={{ borderRadius: 18, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", padding: "14px 16px" }}>
                              <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.42)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{item.label}</p>
                              <p style={{ margin: 0, fontSize: 26, fontWeight: 900, color: item.tone }}>{item.value}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 20 }}>
                        <NextLink
                          href="/marketing/generated-content"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "11px 16px",
                            borderRadius: 14,
                            background: "#fff",
                            color: "#111827",
                            textDecoration: "none",
                            fontWeight: 800,
                            fontSize: 13,
                          }}
                        >
                          <Sparkles size={14} />
                          Open Content Workspace
                        </NextLink>
                        <button onClick={() => setTab("campaigns")} style={{ ...btnSecondary, background: "rgba(255,255,255,0.06)", color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.12)" }}>
                          <Target size={13} />
                          Review Campaign Queue
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {agentEvents.map((evt, i) => {
                  const ac = evt.agent ? (AGENT_COLORS[evt.agent] || "#6366f1") : "#6366f1";
                  if (evt.type === "start") return (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "rgba(99,102,241,0.1)", borderRadius: 10 }}>
                      <Sparkles size={14} color="#818cf8" />
                      <span style={{ fontSize: 13, color: "#a5b4fc", fontWeight: 600 }}>{cleanDisplayText(evt.message) || "Run started"}</span>
                    </div>
                  );
                  if (evt.type === "thinking" || evt.type === "step_complete") return (
                    <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <div style={{ width: 32, height: 32, borderRadius: 10, background: `${ac}20`, border: `1px solid ${ac}40`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 11, fontWeight: 700, color: ac }}>
                        {evt.type === "step_complete" ? "OK" : "..."}
                      </div>
                      <div style={{ flex: 1, background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: "10px 12px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: ac, textTransform: "uppercase" }}>{evt.agent || "Agent"}</span>
                          {evt.step && evt.total_steps && <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginLeft: "auto" }}>Step {evt.step}/{evt.total_steps}</span>}
                        </div>
                        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.7)", margin: 0 }}>{cleanDisplayText(evt.message)}</p>
                        {Array.isArray(evt.data?.readiness) && evt.data.readiness.length > 0 && (
                          <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                            {evt.data.readiness.map((item: any, idx: number) => {
                              const ready = item.state === "ready";
                              const blocked = item.state === "blocked";
                              return (
                                <div key={`${item.platform || idx}-${idx}`} style={{ display: "grid", gap: 5, background: "rgba(255,255,255,0.035)", border: `1px solid ${ready ? "rgba(34,197,94,0.28)" : blocked ? "rgba(245,158,11,0.3)" : "rgba(99,102,241,0.24)"}`, borderRadius: 10, padding: "9px 10px" }}>
                                  <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
                                    <span style={{ color: "#fff", fontSize: 12, fontWeight: 800, textTransform: "capitalize" }}>{cleanDisplayText(item.platform || "channel")}</span>
                                    <span style={{ color: ready ? "#86efac" : blocked ? "#fbbf24" : "#a5b4fc", fontSize: 10, fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.08em" }}>{cleanDisplayText(item.state || "draft_ready")}</span>
                                  </div>
                                  <p style={{ color: "rgba(255,255,255,0.58)", fontSize: 11, lineHeight: 1.45, margin: 0 }}>{cleanDisplayText(item.reason || item.mode || "")}</p>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {Array.isArray(evt.data?.execution_queue) && evt.data.execution_queue.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                            {evt.data.execution_queue.map((item: any, idx: number) => (
                              <span key={`${item.platform || idx}-queue`} style={{ border: "1px solid rgba(255,255,255,0.12)", background: "rgba(15,23,42,0.55)", color: "rgba(255,255,255,0.68)", borderRadius: 999, padding: "5px 8px", fontSize: 11, fontWeight: 700 }}>
                                {item.order || idx + 1}. {cleanDisplayText(item.platform || "asset")} Â· {cleanDisplayText(item.status || "queued")}
                              </span>
                            ))}
                          </div>
                        )}
                        {Array.isArray(evt.data?.next_actions) && evt.data.next_actions.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                            {evt.data.next_actions.map((action: any, idx: number) => (
                              <button
                                key={`${action.action || idx}-${idx}`}
                                onClick={() => {
                                  if (action.action === "open_integrations") setTab("integrations");
                                  else if (action.action === "open_campaigns" || action.action === "approve_campaigns") {
                                    const ids = Array.isArray(evt.data?.campaign_ids) ? evt.data.campaign_ids : [];
                                    loadCampaigns().then((fresh) => {
                                      const id = ids.find((campaignId: string) => fresh.some((campaign) => campaign.id === campaignId)) || fresh[0]?.id;
                                      if (id) setExpanded(id);
                                    });
                                    setTab("campaigns");
                                  }
                                }}
                                style={{ background: "rgba(99,102,241,0.16)", border: "1px solid rgba(129,140,248,0.26)", color: "#c7d2fe", borderRadius: 999, padding: "6px 10px", fontSize: 11, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" }}
                              >
                                {cleanDisplayText(action.label || "Open")}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                  if (evt.type === "complete") return (
                    <div key={i} style={{ background: "rgba(16,185,129,0.1)", borderRadius: 12, border: "1px solid rgba(16,185,129,0.3)", padding: "14px 16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <CheckCircle size={16} color="#10b981" />
                        <span style={{ fontSize: 14, fontWeight: 800, color: "#34d399" }}>{cleanDisplayText(evt.message)}</span>
                      </div>
                      {evt.data?.summary && (
                        <p style={{ fontSize: 12, color: "#d1fae5", lineHeight: 1.6, margin: "0 0 10px", whiteSpace: "pre-wrap" }}>
                          {cleanDisplayText(evt.data.summary)}
                        </p>
                      )}
                      {evt.data && (
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <MetricBadge label="Campaigns" value={evt.data.campaigns_created || 0} color="#10b981" />
                          <MetricBadge label="Assets" value={evt.data.assets_created || 0} color="#0ea5e9" />
                          <MetricBadge label="Analytics" value={evt.data.analytics_source === "real" ? "Real only" : "Pending"} color="#f59e0b" />
                        </div>
                      )}
                      {Array.isArray(evt.data?.next_actions) && evt.data.next_actions.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                          {evt.data.next_actions.map((action: any, idx: number) => (
                            <button
                              key={`${action.action || idx}-complete`}
                              onClick={() => {
                                if (action.action === "open_integrations") setTab("integrations");
                                else if (action.action === "open_campaigns" || action.action === "approve_publish") {
                                  const ids = Array.isArray(evt.data?.campaign_ids) ? evt.data.campaign_ids : [];
                                  loadCampaigns().then((fresh) => {
                                    const id = ids.find((campaignId: string) => fresh.some((campaign) => campaign.id === campaignId)) || fresh[0]?.id;
                                    if (id) setExpanded(id);
                                  });
                                  setTab("campaigns");
                                }
                              }}
                              style={{ background: "#ecfdf5", border: "1px solid rgba(16,185,129,0.28)", color: "#047857", borderRadius: 999, padding: "7px 11px", fontSize: 11, fontWeight: 900, cursor: "pointer", fontFamily: "inherit" }}
                            >
                              {cleanDisplayText(action.label || "Open")}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                  if (evt.type === "error") return (
                    <div key={i} style={{ background: "rgba(239,68,68,0.1)", borderRadius: 10, padding: "10px 12px", display: "flex", gap: 8 }}>
                      <XCircle size={14} color="#ef4444" style={{ flexShrink: 0 }} />
                      <p style={{ fontSize: 12, color: "#fca5a5", margin: 0 }}>{cleanDisplayText(evt.message)}</p>
                    </div>
                  );
                  return (
                    <div key={i} style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", padding: "4px 0" }}>{cleanDisplayText(evt.message)}</div>
                  );
                })}
              </div>
            </div>

            {/* Right panel â€” generated content cards */}
            {false && <div style={{ gridColumn: "1 / -1", gridRow: isMobile ? "3 / 4" : "2 / 3", background: "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(9,14,28,1))", borderTop: "1px solid rgba(255,255,255,0.08)", overflow: "hidden", padding: 18, display: "none", flexDirection: "column", gap: 14, minHeight: 0 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div>
                  <span style={{ fontSize: 11, fontWeight: 800, color: "rgba(255,255,255,0.45)", textTransform: "uppercase", letterSpacing: "0.12em" }}>Generated Content Board</span>
                  <p style={{ fontSize: 12, color: "rgba(255,255,255,0.42)", margin: "6px 0 0" }}>Each campaign gets its own stable card, preview, and action stack so nothing overlaps or gets cut off.</p>
                </div>
                <button onClick={loadCampaigns} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.3)", padding: 4 }}>
                  <RefreshCw size={12} />
                </button>
              </div>

              {campaigns.length === 0 && (
                <div style={{ textAlign: "center", padding: "40px 12px" }}>
                  <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", margin: 0 }}>No campaigns yet. Run the engine to generate content.</p>
                </div>
              )}

              <div className="marketing-scroll marketing-scroll--soft" style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", paddingRight: isMobile ? 0 : 6, display: "grid", gridTemplateColumns: isMobile ? "1fr" : isCompactDesktop ? "repeat(2, minmax(0, 1fr))" : "repeat(3, minmax(0, 1fr))", gap: 18, alignContent: "start" }}>
              {campaigns.map(c => {
                const cfg = campaignDisplayConfig(c);
                const Icon = cfg.icon;
                const isPublishing = publishing?.startsWith(c.id + ":");
                const socialCfg = socialPublishConfig(c);
                const SocialIcon = socialCfg.icon;
                const imgUrl = cardImages[c.id] || c.image_url;
                const isPending = ["draft", "pending_approval", "rejected"].includes(c.status || c.lifecycle_status || "");
                const isAd = c.campaign_type === "google_ads" || c.campaign_type === "meta_ads";
                const previewText = truncateClean(extractContentText(c) || cleanDisplayText(c.content?.meta_description || c.content?.preview_text || ""), 220) || "Generated campaign content will appear here.";

                return (
                  <div key={c.id} style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.065), rgba(255,255,255,0.04))", borderRadius: 22, border: "1px solid rgba(255,255,255,0.12)", overflow: "hidden", display: "grid", gridTemplateRows: "auto auto minmax(0, 1fr) auto", minHeight: 380, maxHeight: 500, boxShadow: "0 18px 40px rgba(2,6,23,0.22)" }}>
                    {/* Card header */}
                    <div style={{ padding: "16px 16px 12px", display: "flex", alignItems: "flex-start", gap: 12, flexShrink: 0 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 8, background: cfg.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <Icon size={14} style={{ color: cfg.color }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
                          <p style={{ fontSize: 13, fontWeight: 800, color: "rgba(255,255,255,0.92)", margin: 0, lineHeight: 1.45, wordBreak: "break-word", maxWidth: "100%" }}>{c.name}</p>
                          <div style={{ flexShrink: 0 }}>
                            <StatusBadge status={effectiveCampaignStatus(c)} />
                          </div>
                        </div>
                        <p style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", margin: "2px 0 0" }}>{cfg.label}</p>
                        <div className="marketing-scroll marketing-scroll--soft" style={{ background: "rgba(0,0,0,0.18)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.06)", padding: "10px 11px", minHeight: 84, maxHeight: 112, overflowY: "auto", overflowX: "hidden", flexShrink: 0 }}>
                          <p style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", margin: 0, lineHeight: 1.55, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {previewText}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Generated image */}
                    {imgUrl && (
                      <div style={{ padding: "0 16px 12px", flexShrink: 0 }}>
                        <img src={imgUrl} alt="Generated" style={{ width: "100%", height: 132, objectFit: "cover", borderRadius: 12, border: "1px solid rgba(255,255,255,0.1)" }} />
                      </div>
                    )}

                    <div className="marketing-scroll marketing-scroll--soft" style={{ minHeight: 0, overflowY: "auto", padding: "0 16px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
                      {renderContentPreview(c)}
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
                        <MetricBadge label="Status" value={cleanDisplayText((effectiveCampaignStatus(c) || "draft").replace(/_/g, " "))} color={cfg.color} />
                        <MetricBadge label="Type" value={cfg.label} color="#94a3b8" />
                        <MetricBadge label="Budget" value={isAd ? `$${budget}` : "Organic"} color="#f59e0b" />
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="marketing-scroll marketing-scroll--soft" style={{ padding: "14px 16px 16px", display: "flex", flexDirection: "column", gap: 8, borderTop: "1px solid rgba(255,255,255,0.08)", background: "rgba(2,6,23,0.18)", overflowY: "auto", overflowX: "hidden" }}>
                      {/* Approve/Reject if pending */}
                      {isPending && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => handleApprove(c.id)} disabled={approving === c.id} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "#16a34a", color: "#fff", border: "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            {approving === c.id ? <Loader2 size={11} /> : <CheckCircle size={11} />} Approve
                          </button>
                          <button onClick={() => handleReject(c.id)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(239,68,68,0.15)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            <XCircle size={11} /> Reject
                          </button>
                        </div>
                      )}

                      {(effectiveCampaignStatus(c)) === "awaiting_final_confirmation" && browserRun?.campaignId === c.id && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={confirmBrowserPublish} disabled={confirmingPublish} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            {confirmingPublish ? <Loader2 size={11} /> : <Send size={11} />} Confirm Publish
                          </button>
                          <button onClick={() => setBrowserRun(null)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(255,255,255,0.06)", color: "#cbd5e1", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            Review Later
                          </button>
                        </div>
                      )}

                      {/* Type-specific publish buttons */}
                      {c.campaign_type === "email" && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => handlePublish(c.id, "email")} disabled={isPublishing} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            {isPublishing ? <Loader2 size={11} /> : <Send size={11} />} Send Campaign
                          </button>
                          <button onClick={() => handleSchedule(c.id, "email")} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(37,99,235,0.15)", color: "#93c5fd", border: "1px solid rgba(37,99,235,0.3)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            <Calendar size={11} /> Schedule
                          </button>
                        </div>
                      )}
                      {(c.campaign_type === "social" || ["linkedin", "twitter", "instagram", "facebook"].includes(c.campaign_type)) && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => handlePublish(c.id, socialCfg.platform)} disabled={isPublishing} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: socialCfg.bg, color: "#fff", border: "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            {isPublishing ? <Loader2 size={11} /> : <SocialIcon size={11} />} {socialCfg.label}
                          </button>
                          <button onClick={() => handleSchedule(c.id, socialCfg.platform)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: socialCfg.softBg, color: socialCfg.softColor, border: socialCfg.softBorder, borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            <Calendar size={11} /> Schedule
                          </button>
                        </div>
                      )}
                      {isAd && (
                        <button onClick={() => handlePublish(c.id, c.campaign_type)} disabled={isPublishing || isPending} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: isPending ? "rgba(245,158,11,0.2)" : "#d97706", color: isPending ? "#fbbf24" : "#fff", border: isPending ? "1px solid rgba(245,158,11,0.4)" : "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: isPending ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                          {isPublishing ? <Loader2 size={11} /> : <Megaphone size={11} />}
                          {isPending ? "Approve First" : "Launch Campaign"}
                        </button>
                      )}
                      {c.campaign_type === "seo_blog" && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button onClick={() => handlePublish(c.id, "wordpress")} disabled={isPublishing} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "#21759b", color: "#fff", border: "none", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            {isPublishing ? <Loader2 size={11} /> : <Globe size={11} />} Publish to WordPress
                          </button>
                          <button onClick={() => handleSchedule(c.id, "wordpress")} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(33,117,155,0.15)", color: "#7dd3fc", border: "1px solid rgba(33,117,155,0.3)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                            <Calendar size={11} /> Schedule
                          </button>
                        </div>
                      )}

                      {/* Universal actions */}
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          onClick={() => handleGenerateImage(c.id)}
                          disabled={generatingImage === c.id}
                          style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(139,92,246,0.15)", color: "#c4b5fd", border: "1px solid rgba(139,92,246,0.3)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
                        >
                          {generatingImage === c.id ? <Loader2 size={11} /> : <Image size={11} />} Generate Image
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              const d = await api.optimizeCampaign(campaignBusinessId(c.id), c.id);
                              showOptimizationToast(d, toast);
                            } catch (e: any) { toast.error(actionErrorMessage(e, "Optimization failed. No optimization result was saved.")); }
                          }}
                          style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, background: "rgba(99,102,241,0.15)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8, padding: "7px", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
                        >
                          <Sparkles size={11} /> Optimize
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
              </div>
            </div>}
          </div>
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            CAMPAIGNS TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "campaigns" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>All Campaigns</h2>
              <button onClick={loadCampaigns} style={{ ...btnSecondary }}>
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            <div style={{ background: "linear-gradient(135deg,#0f172a,#1e1b4b)", borderRadius: 18, border: "1px solid rgba(129,140,248,0.35)", padding: 18, color: "#fff", display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1.2fr 1fr", gap: 16, boxShadow: "0 20px 60px rgba(15,23,42,0.18)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 12, background: "rgba(99,102,241,0.28)", display: "grid", placeItems: "center" }}><Mail size={17} /></div>
                  <div>
                    <p style={{ margin: 0, fontWeight: 900, fontSize: 15 }}>Real Audience Layer</p>
                    <p style={{ margin: "3px 0 0", color: "rgba(226,232,240,0.72)", fontSize: 12 }}>Contacts power email sends, follow-up tasks, lead scoring, and real campaign recipients.</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 14 }}>
                  <MetricBadge label="Contacts" value={contactsLoading ? "..." : contacts.length} color="#a5b4fc" />
                  <MetricBadge label="Consent-ready" value={contacts.filter((contact) => contact.consent_status === "subscribed" || contact.consent_status === "opted_in").length} color="#10b981" />
                  <MetricBadge label="Imported" value={contacts.filter((contact) => contact.source === "csv_import").length} color="#0ea5e9" />
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: isMobile ? "flex-start" : "flex-end", gap: 10, flexWrap: "wrap" }}>
                <input
                  ref={contactFileInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => handleContactCsv(event.target.files?.[0])}
                  style={{ display: "none" }}
                />
                <button onClick={() => contactFileInputRef.current?.click()} disabled={importingContacts} style={{ ...btnPrimary, background: "#6366f1" }}>
                  {importingContacts ? <Loader2 size={14} /> : <Plus size={14} />} Import CSV
                </button>
                <button onClick={loadContacts} style={{ ...btnSecondary, background: "rgba(255,255,255,0.08)", color: "#e2e8f0", borderColor: "rgba(255,255,255,0.16)" }}>
                  <RefreshCw size={13} /> Contacts
                </button>
              </div>
            </div>

            {campaignsLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
                <Loader2 size={28} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : campaigns.length === 0 ? (
              <div style={{ background: "#fff", borderRadius: 18, border: "2px dashed #e2e8f0", padding: "60px 24px", textAlign: "center" }}>
                <Bot size={28} style={{ color: "#6366f1", margin: "0 auto 12px" }} />
                <p style={{ fontWeight: 700, color: "#374151", margin: "0 0 6px" }}>No campaigns yet</p>
                <p style={{ fontSize: 13, color: "#94a3b8", margin: "0 0 16px" }}>Use the Engine tab to generate your first campaign.</p>
                <button onClick={() => setTab("engine")} style={{ ...btnPrimary }}>
                  <Zap size={14} /> Open Engine
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {campaigns.map(c => {
                  const cfg = campaignDisplayConfig(c);
                  const Icon = cfg.icon;
                  const isExp = expanded === c.id;
                  const m = c.metrics || {};
                  const status = effectiveCampaignStatus(c);
                  const isPublishing = publishing?.startsWith(c.id + ":");
                  const socialCfg = socialPublishConfig(c);
                  const SocialIcon = socialCfg.icon;
                  const actionPlatforms = campaignActionPlatforms(c);
                  const isApprovedForActions = !["draft", "pending_approval", "rejected"].includes(status || "");

                  return (
                    <div key={c.id} style={{ background: "#fff", borderRadius: 16, border: status === "pending_approval" ? "1.5px solid #fde68a" : "1px solid #e2e8f0", overflow: "hidden" }}>
                      <button
                        onClick={() => setExpanded(isExp ? null : c.id)}
                        style={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 18px", background: "none", border: "none", cursor: "pointer", textAlign: "left", fontFamily: "inherit" }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <div style={{ width: 36, height: 36, borderRadius: 10, background: cfg.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                            <Icon size={16} style={{ color: cfg.color }} />
                          </div>
                          <div>
                            <p style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", margin: 0 }}>{c.name}</p>
                            <p style={{ fontSize: 11, color: "#94a3b8", margin: "2px 0 0" }}>{cfg.label} &bull; {new Date(c.created_at).toLocaleDateString()}</p>
                          </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {m.clicks > 0 && <MetricBadge label="Clicks" value={m.clicks} color="#0ea5e9" />}
                          {m.conversions > 0 && <MetricBadge label="Conv." value={m.conversions} color="#10b981" />}
                          <StatusBadge status={status} />
                          {isExp ? <ChevronDown size={14} style={{ color: "#94a3b8" }} /> : <ChevronRight size={14} style={{ color: "#94a3b8" }} />}
                        </div>
                      </button>

                      {isExp && (
                        <div style={{ borderTop: "1px solid #f1f5f9", padding: "16px 18px", display: "flex", flexDirection: "column", gap: 14 }}>
                          {/* Metrics row */}
                          {(m.impressions > 0 || m.clicks > 0) && (
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", background: "#f8fafc", borderRadius: 10, padding: "12px 14px" }}>
                              {[
                                ["Impressions", m.impressions?.toLocaleString() || 0, "#6366f1"],
                                ["Clicks", m.clicks || 0, "#0ea5e9"],
                                ["CTR", `${m.ctr || 0}%`, "#f59e0b"],
                                ["Conversions", m.conversions || 0, "#10b981"],
                                ["Spend", `$${((m.spend_cents || 0) / 100).toFixed(2)}`, "#ef4444"],
                              ].map(([l, v, col]) => (
                                <MetricBadge key={String(l)} label={String(l)} value={String(v)} color={String(col)} />
                              ))}
                            </div>
                          )}

                          {/* Content preview */}
                          {c.content && (
                            <div style={{ background: "#f8fafc", borderRadius: 10, padding: "12px 14px" }}>
                              <p style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 8px" }}>Content Preview</p>
                              <p style={{ fontSize: 13, color: "#374151", margin: 0, lineHeight: 1.6 }}>
                                {truncateClean(c.content.subject || c.content.headline || c.content.post_text || c.content.body || cleanDisplayText(c.content), 220)}
                              </p>
                            </div>
                          )}

                          {/* Image */}
                          {(cardImages[c.id] || c.image_url) && (
                            <img src={cardImages[c.id] || c.image_url!} alt="Campaign" style={{ width: "100%", maxHeight: 200, objectFit: "cover", borderRadius: 10, border: "1px solid #e2e8f0" }} />
                          )}

                          {/* Approval row */}
                          {["draft", "pending_approval", "rejected"].includes(status || "") && (
                            <div style={{ display: "flex", gap: 8, padding: "12px 14px", background: "#fffbeb", borderRadius: 12, border: "1px solid #fde68a", alignItems: "center" }}>
                              <AlertTriangle size={14} style={{ color: "#d97706", flexShrink: 0 }} />
                              <p style={{ fontSize: 12, color: "#92400e", margin: 0, flex: 1 }}>Approve this campaign before any live send, publish, or browser automation run.</p>
                              <button onClick={() => handleApprove(c.id)} disabled={approving === c.id} style={{ ...btnGreen, padding: "7px 14px", fontSize: 12 }}>
                                {approving === c.id ? <Loader2 size={12} /> : <CheckCircle size={12} />} Approve
                              </button>
                              <button onClick={() => handleReject(c.id)} style={{ ...btnDanger, padding: "7px 14px", fontSize: 12 }}>
                                <XCircle size={12} /> Reject
                              </button>
                            </div>
                          )}

                          {status === "awaiting_final_confirmation" && browserRun?.campaignId === c.id && (
                            <div style={{ display: "flex", gap: 8, padding: "12px 14px", background: "#eff6ff", borderRadius: 12, border: "1px solid #bfdbfe", alignItems: "center" }}>
                              <Send size={14} style={{ color: "#2563eb", flexShrink: 0 }} />
                              <p style={{ fontSize: 12, color: "#1e3a8a", margin: 0, flex: 1 }}>The browser draft is ready. Confirm when you want the final publish click to happen.</p>
                              <button onClick={confirmBrowserPublish} disabled={confirmingPublish} style={{ ...btnPrimary, padding: "7px 14px", fontSize: 12 }}>
                                {confirmingPublish ? <Loader2 size={12} /> : <Send size={12} />} Confirm Publish
                              </button>
                            </div>
                          )}

                          {/* Action buttons */}
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <NextLink href={`/marketing/generated-content/${c.id}?business_id=${c.business_id || businessId}`} style={{ ...btnPrimary, padding: "8px 13px", fontSize: 12, textDecoration: "none" }}>
                              <Sparkles size={13} /> Open Workspace
                            </NextLink>
                            <button onClick={() => handleGenerateImage(c.id)} disabled={generatingImage === c.id} style={{ ...btnSecondary }}>
                              {generatingImage === c.id ? <Loader2 size={13} /> : <Image size={13} />} Generate Image
                            </button>
                            <button
                              onClick={async () => {
                                try {
                                  const d = await api.optimizeCampaign(campaignBusinessId(c.id), c.id);
                                  showOptimizationToast(d, toast);
                                } catch (e: any) { toast.error(actionErrorMessage(e, "Optimization failed. No optimization result was saved.")); }
                              }}
                              style={{ ...btnSecondary }}
                            >
                              <Sparkles size={13} /> Optimize with AI
                            </button>
                            {c.campaign_type === "email" && (
                              <>
                                <button onClick={() => handlePublish(c.id, "email")} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnPrimary, padding: "7px 14px", fontSize: 12, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={12} /> : <Send size={12} />} Send Campaign
                                </button>
                                <button onClick={() => handlePublish(c.id, "email_browser")} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnSecondary, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={13} /> : <Bot size={13} />} Browser Draft
                                </button>
                                <button onClick={() => handleSchedule(c.id, "email")} style={{ ...btnSecondary }}>
                                  <Calendar size={13} /> Schedule
                                </button>
                              </>
                            )}
                            {c.campaign_type === "multi_channel" && actionPlatforms.length > 0 && (
                              <div style={{ flexBasis: "100%", display: "grid", gap: 8, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: 12 }}>
                                <p style={{ margin: 0, color: "#475569", fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>Platform assets</p>
                                {actionPlatforms.map((platform) => {
                                  const cfg = platform === "email"
                                    ? { label: "Email asset", icon: Mail, color: "#2563eb" }
                                    : platform === "wordpress"
                                      ? { label: "WordPress asset", icon: Globe, color: "#21759b" }
                                      : socialPublishConfig({ ...c, targeting: { ...(c.targeting || {}), platform }, content: { ...(c.content || {}), platform } } as MarketingCampaign);
                                  const Icon = cfg.icon;
                                  const cfgColor = "color" in cfg ? cfg.color : cfg.bg;
                                  const canPublish = isApprovedForActions;
                                  return (
                                    <div key={platform} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "9px 10px" }}>
                                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: cfgColor, fontSize: 12, fontWeight: 900, minWidth: 122 }}>
                                        <Icon size={13} /> {cfg.label}
                                      </span>
                                      {platform === "email" ? (
                                        <>
                                          <button onClick={() => handlePublish(c.id, "email")} disabled={!!isPublishing || !canPublish} style={{ ...btnPrimary, padding: "7px 12px", fontSize: 12, opacity: canPublish ? 1 : 0.55 }}>
                                            <Send size={12} /> Send
                                          </button>
                                          <button onClick={() => handlePublish(c.id, "email_browser")} disabled={!!isPublishing || !canPublish} style={{ ...btnSecondary, opacity: canPublish ? 1 : 0.55 }}>
                                            <Bot size={13} /> Gmail Draft
                                          </button>
                                        </>
                                      ) : platform === "wordpress" ? (
                                        <>
                                          <button onClick={() => handlePublish(c.id, "wordpress")} disabled={!!isPublishing || !canPublish} style={{ ...btnPrimary, background: "#21759b", padding: "7px 12px", fontSize: 12, opacity: canPublish ? 1 : 0.55 }}>
                                            <Globe size={12} /> Publish
                                          </button>
                                          <button onClick={() => handlePublish(c.id, "wordpress_browser")} disabled={!!isPublishing || !canPublish} style={{ ...btnSecondary, opacity: canPublish ? 1 : 0.55 }}>
                                            <Bot size={13} /> Browser
                                          </button>
                                        </>
                                      ) : (
                                        <>
                                          <button onClick={() => handlePublish(c.id, platform)} disabled={!!isPublishing || !canPublish} style={{ ...btnPrimary, background: cfgColor, padding: "7px 12px", fontSize: 12, opacity: canPublish ? 1 : 0.55 }}>
                                            <Icon size={12} /> API Publish
                                          </button>
                                          <button onClick={() => handlePublish(c.id, `${platform}_browser`)} disabled={!!isPublishing || !canPublish} style={{ ...btnSecondary, opacity: canPublish ? 1 : 0.55 }}>
                                            <Bot size={13} /> Browser
                                          </button>
                                        </>
                                      )}
                                      {!canPublish && <span style={{ color: "#b45309", fontSize: 11, fontWeight: 800 }}>Approve first</span>}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                            {(c.campaign_type === "social" || ["linkedin", "twitter", "instagram", "facebook"].includes(c.campaign_type)) && (
                              <>
                                <button onClick={() => handlePublish(c.id, socialCfg.platform)} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnPrimary, background: socialCfg.bg, padding: "7px 14px", fontSize: 12, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={12} /> : <SocialIcon size={12} />} {socialCfg.label}
                                </button>
                                <button onClick={() => handlePublish(c.id, `${socialCfg.platform}_browser`)} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnSecondary, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={13} /> : <Bot size={13} />} Browser Agent
                                </button>
                                <button onClick={() => handleSchedule(c.id, socialCfg.platform)} style={{ ...btnSecondary }}>
                                  <Calendar size={13} /> Schedule
                                </button>
                              </>
                            )}
                            {(c.campaign_type === "google_ads" || c.campaign_type === "meta_ads") && (
                              <button onClick={() => handlePublish(c.id, c.campaign_type)} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnPrimary, background: "#d97706", padding: "7px 14px", fontSize: 12, opacity: isApprovedForActions ? 1 : 0.5, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                {isPublishing ? <Loader2 size={12} /> : <Megaphone size={12} />} Launch Campaign
                              </button>
                            )}
                            {c.campaign_type === "seo_blog" && (
                              <>
                                <button onClick={() => handlePublish(c.id, "wordpress")} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnPrimary, background: "#21759b", padding: "7px 14px", fontSize: 12, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={12} /> : <Globe size={12} />} Publish to WordPress
                                </button>
                                <button onClick={() => handlePublish(c.id, "wordpress_browser")} disabled={!!isPublishing || !isApprovedForActions} style={{ ...btnSecondary, opacity: isApprovedForActions ? 1 : 0.55, cursor: isApprovedForActions ? "pointer" : "not-allowed" }}>
                                  {isPublishing ? <Loader2 size={13} /> : <Bot size={13} />} Browser Agent
                                </button>
                                <button onClick={() => handleSchedule(c.id, "wordpress")} style={{ ...btnSecondary }}>
                                  <Calendar size={13} /> Schedule
                                </button>
                              </>
                            )}
                          </div>

                          {c.rejection_reason && (
                            <p style={{ fontSize: 12, color: "#dc2626", background: "#fef2f2", borderRadius: 8, padding: "8px 10px", margin: 0 }}>
                              Rejected: {c.rejection_reason}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            CONTENT STUDIO TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "content-studio" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
            <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Content Studio</h2>

              <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
                {/* Content type */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Content Type</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {CONTENT_TYPES.map(ct => (
                      <button
                        key={ct.id}
                        onClick={() => setContentType(ct.id)}
                        style={{ padding: "7px 14px", borderRadius: 99, fontSize: 12, fontWeight: 600, border: `1.5px solid ${contentType === ct.id ? "#6366f1" : "#e2e8f0"}`, background: contentType === ct.id ? "#ede9fe" : "#f8fafc", color: contentType === ct.id ? "#6366f1" : "#64748b", cursor: "pointer", fontFamily: "inherit" }}
                      >
                        {ct.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tone */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Tone of Voice</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {TONES.map(t => (
                      <button
                        key={t}
                        onClick={() => setTone(t)}
                        style={{ padding: "7px 14px", borderRadius: 99, fontSize: 12, fontWeight: 600, border: `1.5px solid ${tone === t ? "#0ea5e9" : "#e2e8f0"}`, background: tone === t ? "#e0f2fe" : "#f8fafc", color: tone === t ? "#0369a1" : "#64748b", cursor: "pointer", fontFamily: "inherit" }}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Target audience */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Target Audience</label>
                  <input
                    value={audience}
                    onChange={e => setAudience(e.target.value)}
                    placeholder="e.g. SaaS founders, marketing managers, e-commerce owners..."
                    style={inputStyle}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Featured Product</label>
                  <select
                    value={selectedProductId}
                    onChange={(e) => setSelectedProductId(e.target.value)}
                    style={inputStyle}
                    disabled={productsLoading}
                  >
                    <option value="">No specific product</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.price} {product.currency?.toUpperCase()})
                      </option>
                    ))}
                  </select>
                </div>

                {/* CTA */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Call to Action</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {CTAS.map(c => (
                      <button
                        key={c}
                        onClick={() => setCta(c)}
                        style={{ padding: "7px 14px", borderRadius: 99, fontSize: 12, fontWeight: 600, border: `1.5px solid ${cta === c ? "#10b981" : "#e2e8f0"}`, background: cta === c ? "#dcfce7" : "#f8fafc", color: cta === c ? "#16a34a" : "#64748b", cursor: "pointer", fontFamily: "inherit" }}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Goal / topic */}
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Topic / Goal</label>
                  <textarea
                    value={contentGoal}
                    onChange={e => setContentGoal(e.target.value)}
                    rows={3}
                    placeholder="Describe what you want to communicate..."
                    style={{ ...inputStyle, resize: "none" }}
                  />
                </div>

                <button
                  onClick={handleGenerateContent}
                  disabled={generatingContent || !contentGoal.trim() || !businessId}
                  style={{ ...btnPrimary, opacity: (generatingContent || !contentGoal.trim() || !businessId) ? 0.6 : 1, cursor: (generatingContent || !contentGoal.trim() || !businessId) ? "not-allowed" : "pointer" }}
                >
                  {generatingContent ? <><Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} /> Generating...</> : <><Sparkles size={15} /> Generate Content</>}
                  <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
                </button>
              </div>

              {/* Generated result */}
              {generatedContent && (
                <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 24 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                      <CheckCircle size={16} style={{ color: "#10b981" }} /> Generated Content
                    </h3>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                      <button
                        onClick={() => {
                          const text = extractContentText(generatedContent);
                          navigator.clipboard.writeText(text).catch(() => {});
                        }}
                        style={{ ...btnSecondary }}
                      >
                        Copy
                      </button>
                      {generatedContent.id && generatedContent.campaign_type !== "email" && generatedContent.campaign_type !== "google_ads" && generatedContent.campaign_type !== "meta_ads" && (
                        <button onClick={() => handlePublish(generatedContent.id, `${generatedContent.content?.platform || "linkedin"}_browser`)} style={{ ...btnSecondary }}>
                          <Globe size={13} /> Post using Browser Agent
                        </button>
                      )}
                      {generatedContent.id && ["draft", "pending_approval", "rejected"].includes(generatedContent.status || generatedContent.lifecycle_status || "") && (
                        <button onClick={() => handleApprove(generatedContent.id)} disabled={approving === generatedContent.id} style={{ ...btnGreen, padding: "7px 14px", fontSize: 12 }}>
                          {approving === generatedContent.id ? <Loader2 size={13} /> : <CheckCircle size={13} />} Approve
                        </button>
                      )}
                      <button onClick={() => setTab("campaigns")} style={{ ...btnPrimary, padding: "7px 14px", fontSize: 12 }}>
                        View in Campaigns
                      </button>
                    </div>
                  </div>
                  {renderContentPreview(generatedContent)}
                  {generatedContent.name && (
                    <p style={{ fontSize: 12, color: "#94a3b8", margin: "10px 0 0" }}>Campaign: {generatedContent.name}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            ANALYTICS TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "analytics" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Analytics</h2>
              <button onClick={loadAnalytics} style={{ ...btnSecondary }}>
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            {analyticsLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
                <Loader2 size={28} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : !analytics ? (
              <div style={{ background: "#fff", borderRadius: 18, border: "2px dashed #e2e8f0", padding: "60px 24px", textAlign: "center" }}>
                <BarChart3 size={28} style={{ color: "#6366f1", margin: "0 auto 12px" }} />
                <p style={{ fontWeight: 700, color: "#374151", margin: "0 0 6px" }}>No analytics data yet</p>
                <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>Waiting for real campaign events from sends, clicks, conversions, and payments.</p>
              </div>
            ) : (
              <>
                {/* Stat cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16 }}>
                  {[
                    { label: "Total Impressions", value: (analytics.total_impressions || 0).toLocaleString(), color: "#6366f1", icon: <TrendingUp size={18} /> },
                    { label: "Total Clicks",      value: (analytics.total_clicks || 0).toLocaleString(),      color: "#0ea5e9", icon: <Target size={18} /> },
                    { label: "CTR",               value: `${(analytics.ctr || 0).toFixed(2)}%`,               color: "#f59e0b", icon: <BarChart3 size={18} /> },
                    { label: "Conversions",       value: (analytics.total_conversions || 0).toLocaleString(), color: "#10b981", icon: <CheckCircle size={18} /> },
                    { label: "Real Revenue",      value: `$${(analytics.total_revenue_usd || 0).toFixed(2)}`, color: "#f59e0b", icon: <Zap size={18} /> },
                  ].map(({ label, value, color, icon }) => (
                    <div key={label} style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", padding: "20px", display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>{label}</span>
                        <div style={{ color, opacity: 0.7 }}>{icon}</div>
                      </div>
                      <span style={{ fontSize: 26, fontWeight: 900, color }}>{value}</span>
                    </div>
                  ))}
                </div>

                {/* Campaign performance table */}
                {analytics.campaigns && analytics.campaigns.length > 0 && (
                  <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
                    <div style={{ padding: "16px 20px", borderBottom: "1px solid #f1f5f9" }}>
                      <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Campaign Performance</h3>
                    </div>
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                        <thead>
                          <tr style={{ background: "#f8fafc" }}>
                            {["Campaign", "Type", "Source", "Clicks", "CTR", "Conversions", "Revenue"].map(h => (
                              <th key={h} style={{ padding: "10px 16px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {analytics.campaigns.map((c, i) => (
                            <tr key={c.id} style={{ borderTop: "1px solid #f1f5f9", background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
                              <td style={{ padding: "12px 16px", fontWeight: 600, color: "#0f172a" }}>{c.name}</td>
                              <td style={{ padding: "12px 16px" }}>
                                <span style={{ background: campaignTypeConfig(c.type).bg, color: campaignTypeConfig(c.type).color, fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 99 }}>{c.type}</span>
                              </td>
                              <td style={{ padding: "12px 16px", color: "#64748b", fontWeight: 700 }}>{c.analytics_source || "real"}</td>
                              <td style={{ padding: "12px 16px", color: "#0ea5e9", fontWeight: 600 }}>{(c.clicks || 0).toLocaleString()}</td>
                              <td style={{ padding: "12px 16px", color: "#f59e0b", fontWeight: 600 }}>{(c.ctr || 0).toFixed(2)}%</td>
                              <td style={{ padding: "12px 16px", color: "#10b981", fontWeight: 600 }}>{c.conversions || 0}</td>
                              <td style={{ padding: "12px 16px", color: "#f59e0b", fontWeight: 600 }}>${(c.revenue_usd || 0).toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* AI Insights */}
                {analytics.insights && analytics.insights.length > 0 && (
                  <div style={{ background: "linear-gradient(135deg,#ede9fe,#dbeafe)", borderRadius: 18, border: "1px solid #c7d2fe", padding: 24 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 800, color: "#4338ca", margin: "0 0 14px", display: "flex", alignItems: "center", gap: 8 }}>
                      <Sparkles size={16} /> AI Insights
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {analytics.insights.map((insight, i) => (
                        <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#6366f1", marginTop: 6, flexShrink: 0 }} />
                          <p style={{ fontSize: 13, color: "#374151", margin: 0, lineHeight: 1.6 }}>{cleanDisplayText(insight)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            INTEGRATIONS TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "integrations" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Integrations</h2>
              <button onClick={loadIntegrations} style={{ ...btnSecondary }}>
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            {integrationsLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
                <Loader2 size={28} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
                  {sortedIntegrationPlatforms.map((platform, index) => {
                    const integration = getIntegration(platform.id);
                    const isEnvBacked = platform.id === "sendgrid";
                    const status = platform.id === "sendgrid" && integration?.ready_to_connect !== false
                      ? "connected"
                      : integration?.status || "disconnected";
                    const sc = integrationStateMeta(platform.id === "sendgrid" && integration?.ready_to_connect !== false ? { ...integration, status: "connected", state_label: "connected" } as IntegrationStatus : integration);
                    const groupLabel = integrationGroupLabel(platform.id);
                    const previousGroupLabel = index > 0 ? integrationGroupLabel(sortedIntegrationPlatforms[index - 1].id) : "";

                    return (
                      <div key={platform.id} style={{ display: "contents" }}>
                      {groupLabel !== previousGroupLabel && (
                        <div style={{ gridColumn: "1 / -1", marginTop: index === 0 ? 0 : 8, display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ height: 1, flex: 1, background: "linear-gradient(90deg, transparent, #cbd5e1)" }} />
                          <span style={{ fontSize: 12, fontWeight: 900, color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em" }}>{groupLabel}</span>
                          <div style={{ height: 1, flex: 1, background: "linear-gradient(90deg, #cbd5e1, transparent)" }} />
                        </div>
                      )}
                      <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                      {/* Header */}
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <PlatformIcon platform={platform.id} size={40} />
                        <div style={{ flex: 1 }}>
                          <p style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", margin: 0 }}>{platform.label}</p>
                          {integration?.account_name && (
                            <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>{integration.account_name}</p>
                          )}
                        </div>
                        <span style={{ background: sc.bg, color: sc.color, fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 99 }}>{sc.title}</span>
                      </div>

                      {integration?.connection_error && (
                        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 10, padding: "10px 12px", fontSize: 12, color: "#9a3412", lineHeight: 1.5 }}>
                          {integration.connection_error}
                        </div>
                      )}

                      {!platform.apiKey && (
                        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "10px 12px", display: "grid", gap: 8 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                            <span style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em" }}>Official OAuth</span>
                            <span style={{ fontSize: 11, fontWeight: 800, color: integration?.ready_to_connect === false ? "#d97706" : "#16a34a" }}>
                              {integration?.ready_to_connect === false ? "App config needed" : "User-safe connect"}
                            </span>
                          </div>
                          {integration?.scopes?.length ? (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                              {integration.scopes.slice(0, 4).map((scope: string) => (
                                <span key={scope} style={{ background: "#eef2ff", color: "#4f46e5", borderRadius: 999, padding: "4px 8px", fontSize: 11, fontWeight: 700 }}>{scope}</span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      )}

                      {/* Connect / Disconnect */}
                      {status === "connected" ? (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                          {["gmail", "sendgrid", "notion"].includes(platform.id) && (
                            <button
                              onClick={() => handleProviderToolTest(platform.id)}
                              style={{ ...btnPrimary, justifyContent: "center", gridColumn: "1 / -1", background: platform.color }}
                            >
                              <Send size={13} /> {platform.id === "notion" ? "Create Test Page" : "Send Test Email"}
                            </button>
                          )}
                          <button
                            onClick={() => handleTestOAuth(platform.id)}
                            disabled={testingOAuth === platform.id}
                            style={{ ...btnSecondary, justifyContent: "center", gridColumn: isEnvBacked ? "1 / -1" : undefined }}
                          >
                            {testingOAuth === platform.id ? <Loader2 size={13} /> : <CheckCircle size={13} />} {isEnvBacked ? "Test Server Config" : "Test"}
                          </button>
                          {!isEnvBacked && (
                            <>
                              <button
                                onClick={() => handleRefreshOAuth(platform.id)}
                                disabled={refreshingOAuth === platform.id}
                                style={{ ...btnSecondary, justifyContent: "center" }}
                              >
                                {refreshingOAuth === platform.id ? <Loader2 size={13} /> : <RefreshCw size={13} />} Refresh
                              </button>
                              <button
                                onClick={() => handleDisconnect(platform.id)}
                                style={{ ...btnDanger, justifyContent: "center", gridColumn: "1 / -1" }}
                              >
                                <XCircle size={13} /> Disconnect
                              </button>
                            </>
                          )}
                        </div>
                      ) : (
                        !platform.apiKey && (
                          <button
                            onClick={() => handleConnect(platform.id)}
                            disabled={integration?.ready_to_connect === false}
                            style={{ ...btnPrimary, background: integration?.ready_to_connect === false ? "#94a3b8" : platform.color, opacity: integration?.ready_to_connect === false ? 0.72 : 1, cursor: integration?.ready_to_connect === false ? "not-allowed" : "pointer" }}
                          >
                            <LinkIcon size={13} /> {integration?.ready_to_connect === false ? "Developer setup required" : `Connect ${platform.label}`}
                          </button>
                        )
                      )}

                      {platform.id === "sendgrid" && status === "connected" && (
                        <div style={{ fontSize: 12, lineHeight: 1.55, color: "#64748b" }}>
                          SendGrid is managed privately on the backend. Users only choose approved campaign recipients.
                        </div>
                      )}

                      {!platform.apiKey && (
                        <div style={{ fontSize: 12, lineHeight: 1.55, color: "#64748b" }}>
                          OAuth is handled by the backend. Users only authorize their account on the provider page.
                        </div>
                      )}

                      {status === "expired" && (
                        <div style={{ display: "flex", gap: 8 }}>
                          <button onClick={() => handleConnect(platform.id)} style={{ ...btnPrimary, flex: 1, fontSize: 12 }}>
                            <RefreshCw size={12} /> Reconnect
                          </button>
                          <button onClick={() => handleDisconnect(platform.id)} style={{ ...btnDanger, flex: 1, fontSize: 12 }}>
                            <XCircle size={12} /> Remove
                          </button>
                        </div>
                      )}
                      </div>
                      </div>
                    );
                  })}
                </div>

                <div style={{ background: "linear-gradient(180deg,#ffffff 0%,#f8fafc 100%)", borderRadius: 18, border: "1px solid #e2e8f0", padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <div>
                      <h3 style={{ fontSize: 15, fontWeight: 900, color: "#0f172a", margin: 0 }}>Integration activity</h3>
                      <p style={{ fontSize: 13, color: "#64748b", margin: "5px 0 0" }}>A real audit trail of OAuth, tests, refreshes, and AI tool publishing attempts.</p>
                    </div>
                    {integrationLogsLoading ? <Loader2 size={16} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} /> : null}
                  </div>

                  {integrationLogs.length === 0 ? (
                    <div style={{ border: "1px dashed #cbd5e1", borderRadius: 14, padding: 18, color: "#64748b", fontSize: 13, background: "#f8fafc" }}>
                      No integration actions have been recorded yet. Connect a provider or run a publish/test action to populate this trail.
                    </div>
                  ) : (
                    <div style={{ display: "grid", gap: 10, maxHeight: 320, overflowY: "auto", paddingRight: 4 }}>
                      {integrationLogs.map((log) => {
                        const tone =
                          log.status === "success" || log.status === "connected"
                            ? { bg: "#dcfce7", color: "#16a34a", label: "Success" }
                            : log.status === "failed" || log.status === "expired"
                              ? { bg: "#fee2e2", color: "#dc2626", label: "Failed" }
                              : log.status === "blocked"
                                ? { bg: "#fef3c7", color: "#d97706", label: "Blocked" }
                                : { bg: "#eef2ff", color: "#4f46e5", label: log.status || "Pending" };
                        return (
                          <div key={log.id} style={{ border: "1px solid #e2e8f0", borderRadius: 14, padding: 14, background: "#fff", display: "grid", gap: 8 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                                <PlatformIcon platform={log.provider} size={30} />
                                <div style={{ minWidth: 0 }}>
                                  <p style={{ fontSize: 13, fontWeight: 900, color: "#0f172a", margin: 0, textTransform: "capitalize" }}>{log.provider} Â· {log.action.replaceAll("_", " ")}</p>
                                  <p style={{ fontSize: 12, color: "#64748b", margin: "3px 0 0" }}>{log.created_at ? new Date(log.created_at).toLocaleString() : "Just now"}</p>
                                </div>
                              </div>
                              <span style={{ background: tone.bg, color: tone.color, borderRadius: 999, padding: "4px 9px", fontSize: 11, fontWeight: 900 }}>{tone.label}</span>
                            </div>
                            {log.message ? <p style={{ fontSize: 13, color: "#334155", margin: 0, lineHeight: 1.55 }}>{log.message}</p> : null}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
                    <div>
                      <h3 style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", margin: 0 }}>Browser account vault</h3>
                      <p style={{ fontSize: 13, color: "#64748b", margin: "6px 0 0", lineHeight: 1.6 }}>
                        Save the private login details the browser operator should use when it needs to restore a live session for posting, verification, or inbox work.
                      </p>
                    </div>
                    {integrationAccountsLoading ? (
                      <span style={{ fontSize: 12, color: "#6366f1", fontWeight: 700 }}>Loading accounts...</span>
                    ) : null}
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
                    {ACCOUNT_VAULT_PLATFORMS.map((vault) => {
                      const account = getIntegrationAccount(vault.id);
                      const status = account?.status || "disconnected";
                      const stateColor =
                        status === "connected"
                          ? { bg: "#dcfce7", color: "#16a34a", title: "Connected" }
                          : status === "error"
                            ? { bg: "#fee2e2", color: "#dc2626", title: "Needs attention" }
                            : { bg: "#eef2ff", color: "#4f46e5", title: "Not saved" };

                      return (
                        <div key={vault.id} style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: 18, background: "linear-gradient(180deg,#ffffff 0%,#f8fafc 100%)", display: "flex", flexDirection: "column", gap: 12 }}>
                          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                            <PlatformIcon platform={vault.id === "gmail" ? "sendgrid" : vault.id === "browser_automation" ? "wordpress" : vault.id} size={40} />
                            <div style={{ flex: 1 }}>
                              <p style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>{vault.label}</p>
                              <p style={{ fontSize: 12, color: "#64748b", margin: "4px 0 0", lineHeight: 1.5 }}>{vault.hint}</p>
                            </div>
                          </div>

                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                            <span style={{ background: stateColor.bg, color: stateColor.color, fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 999 }}>{stateColor.title}</span>
                            {account?.identifier_preview ? (
                              <span style={{ fontSize: 12, color: "#64748b" }}>{account.identifier_preview}</span>
                            ) : (
                              <span style={{ fontSize: 12, color: "#94a3b8" }}>No account saved yet</span>
                            )}
                          </div>

                          {account?.last_error ? (
                            <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 10, padding: "10px 12px", fontSize: 12, color: "#9a3412", lineHeight: 1.5 }}>
                              {account.last_error}
                            </div>
                          ) : null}

                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button onClick={() => openAccountModal(vault.id)} style={{ ...btnPrimary, flex: 1, minWidth: 150 }}>
                              <Settings size={13} /> Manage account
                            </button>
                            <button onClick={() => testSavedAccount(vault.id)} disabled={testingAccount === vault.id || !account?.id} style={{ ...btnSecondary, flex: 1, minWidth: 150, opacity: account?.id ? 1 : 0.55, cursor: account?.id ? "pointer" : "not-allowed" }}>
                              {testingAccount === vault.id ? <Loader2 size={13} /> : <RefreshCw size={13} />} Test
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            CALENDAR TAB
        â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {tab === "calendar" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Content Calendar</h2>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={handleCalendarSync} disabled={syncingCalendar} style={{ ...btnPrimary, padding: "8px 13px" }}>
                  {syncingCalendar ? <Loader2 size={13} /> : <Calendar size={13} />} Sync Google Calendar
                </button>
                <button onClick={loadCalendar} style={{ ...btnSecondary }}>
                  <RefreshCw size={13} /> Refresh
                </button>
              </div>
            </div>

            {calendarLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
                <Loader2 size={28} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
                <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : calendarPosts.length === 0 ? (
              <div style={{ background: "#fff", borderRadius: 18, border: "2px dashed #e2e8f0", padding: "60px 24px", textAlign: "center" }}>
                <Calendar size={28} style={{ color: "#6366f1", margin: "0 auto 12px" }} />
                <p style={{ fontWeight: 700, color: "#374151", margin: "0 0 6px" }}>No scheduled posts</p>
                <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>Schedule campaigns from the Engine or Campaigns tab.</p>
              </div>
            ) : (() => {
              // Group by date
              const grouped: Record<string, CalendarPost[]> = {};
              calendarPosts.forEach(post => {
                const date = new Date(post.scheduled_at_utc).toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
                if (!grouped[date]) grouped[date] = [];
                grouped[date].push(post);
              });

              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                  {Object.entries(grouped).map(([date, posts]) => (
                    <div key={date}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                        <div style={{ height: 1, flex: 1, background: "#e2e8f0" }} />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b", whiteSpace: "nowrap" }}>{date}</span>
                        <div style={{ height: 1, flex: 1, background: "#e2e8f0" }} />
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {posts.map(post => {
                          let contentPreview = "";
                          const rawContent = post.content_json || post.description || post.title || "";
                          try {
                            const parsed = JSON.parse(rawContent);
                            contentPreview = parsed.post_text || parsed.body || parsed.subject || parsed.headline || "";
                          } catch { contentPreview = rawContent; }
                          contentPreview = truncateClean(contentPreview, 80);

                          const time = new Date(post.scheduled_at_utc).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

                          return (
                            <div key={post.id} style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0", padding: "14px 16px", display: "flex", alignItems: "center", gap: 14 }}>
                              <PlatformIcon platform={post.platform} size={36} />
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontSize: 13, color: "#374151", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {cleanDisplayText(contentPreview) || "(No preview available)"}
                                </p>
                                {post.campaign_name && (
                                  <p style={{ fontSize: 11, color: "#94a3b8", margin: "3px 0 0" }}>{post.campaign_name}</p>
                                )}
                              </div>
                              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4, flexShrink: 0 }}>
                                <span style={{ fontSize: 12, fontWeight: 700, color: "#374151" }}>{time}</span>
                                <StatusBadge status={post.status} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        )}

      </div>{/* end main content */}

      {emailSendModal && (
        <>
          <div onClick={() => setEmailSendModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 94 }} />
          <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(640px, calc(100vw - 32px))", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 95, padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Send Campaign</p>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Email recipients</h3>
              </div>
              <button onClick={() => setEmailSendModal(null)} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <p style={{ fontSize: 13, color: "#475569", margin: 0 }}>Enter one or more recipient emails separated by commas.</p>
              <textarea value={emailSendModal.recipients} onChange={(e) => setEmailSendModal({ ...emailSendModal, recipients: e.target.value })} rows={4} placeholder="founder@example.com, team@example.com" style={{ ...inputStyle, resize: "vertical", minHeight: 120 }} />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button onClick={() => setEmailSendModal(null)} style={{ ...btnSecondary }}>Cancel</button>
                <button onClick={submitEmailSend} style={{ ...btnPrimary }}>
                  <Send size={14} /> Send Campaign
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {publishDetailsModal && (
        <>
          <div onClick={() => setPublishDetailsModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 94 }} />
          <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(640px, calc(100vw - 32px))", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 95, padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#4f46e5", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Official API Publishing</p>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>{publishDetailsModal.title}</h3>
              </div>
              <button onClick={() => setPublishDetailsModal(null)} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <p style={{ fontSize: 13, color: "#475569", margin: 0, lineHeight: 1.6 }}>
                This uses the connected OAuth account. Enter the platform-specific destination details required by the official API.
              </p>
              {publishDetailsModal.fields.map((field) => (
                <label key={field.key} style={{ display: "grid", gap: 7 }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: "#374151" }}>{field.label}{field.required ? " *" : ""}</span>
                  <input
                    value={publishDetailsModal.values[field.key] || ""}
                    onChange={(e) => setPublishDetailsModal({
                      ...publishDetailsModal,
                      values: { ...publishDetailsModal.values, [field.key]: e.target.value },
                    })}
                    placeholder={field.placeholder}
                    style={inputStyle}
                  />
                </label>
              ))}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button onClick={() => setPublishDetailsModal(null)} style={{ ...btnSecondary }}>Cancel</button>
                <button onClick={submitPublishDetails} disabled={!!publishing} style={{ ...btnPrimary }}>
                  {publishing ? <Loader2 size={14} /> : <Send size={14} />} Approve & Publish
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {scheduleModal && (
        <>
          <div onClick={() => setScheduleModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 94 }} />
          <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(560px, calc(100vw - 32px))", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 95, padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Schedule Campaign</p>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Choose publish time</h3>
              </div>
              <button onClick={() => setScheduleModal(null)} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: "#374151" }}>Scheduled date and time</label>
              <input type="datetime-local" value={scheduleModal.scheduledAt} onChange={(e) => setScheduleModal({ ...scheduleModal, scheduledAt: e.target.value })} style={inputStyle} />
              <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>Timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button onClick={() => setScheduleModal(null)} style={{ ...btnSecondary }}>Cancel</button>
                <button onClick={submitSchedule} style={{ ...btnPrimary }}>
                  <Calendar size={14} /> Save Schedule
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {rejectModal && (
        <>
          <div onClick={() => setRejectModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 94 }} />
          <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(560px, calc(100vw - 32px))", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 95, padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#dc2626", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Reject Campaign</p>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>Share feedback</h3>
              </div>
              <button onClick={() => setRejectModal(null)} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <textarea value={rejectModal.reason} onChange={(e) => setRejectModal({ ...rejectModal, reason: e.target.value })} rows={4} placeholder="Tell the team what should change before approval..." style={{ ...inputStyle, resize: "vertical", minHeight: 120 }} />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button onClick={() => setRejectModal(null)} style={{ ...btnSecondary }}>Cancel</button>
                <button onClick={submitReject} style={{ ...btnDanger }}>
                  <XCircle size={14} /> Reject Campaign
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      <IntegrationAccountModal
        account={accountModal}
        saving={savingAccount === accountModal?.platform}
        testing={testingAccount === accountModal?.platform}
        deleting={deletingAccount === accountModal?.platform}
        onClose={() => setAccountModal(null)}
        onChange={setAccountModal}
        onSave={saveAccountCredentials}
        onTest={() => accountModal && testSavedAccount(accountModal.platform)}
        onDelete={() => accountModal && deleteSavedAccount(accountModal.platform)}
      />

      {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
          BRAND SETTINGS PANEL (slide-in)
      â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
      {brandPanelOpen && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setBrandPanelOpen(false)}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 99 }}
          />
          {/* Panel */}
          <div style={{ position: "fixed", right: 0, top: 0, width: 400, height: "100vh", background: "#fff", zIndex: 100, boxShadow: "-8px 0 40px rgba(0,0,0,0.15)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Panel header */}
            <div style={{ padding: "20px 24px", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Settings size={15} color="#fff" />
                </div>
                <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>Brand Settings</h2>
              </div>
              <button onClick={() => setBrandPanelOpen(false)} style={{ background: "#f1f5f9", border: "none", borderRadius: 8, width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", fontSize: 16, color: "#64748b" }}>x</button>
            </div>

            {/* Panel body */}
            <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Colors */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Primary Color</label>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input type="color" value={brand.primary_color} onChange={e => setBrand(b => ({ ...b, primary_color: e.target.value }))} style={{ width: 40, height: 36, borderRadius: 8, border: "1.5px solid #e2e8f0", cursor: "pointer", padding: 2 }} />
                    <input value={brand.primary_color} onChange={e => setBrand(b => ({ ...b, primary_color: e.target.value }))} style={{ ...inputStyle, flex: 1 }} />
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Secondary Color</label>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input type="color" value={brand.secondary_color} onChange={e => setBrand(b => ({ ...b, secondary_color: e.target.value }))} style={{ width: 40, height: 36, borderRadius: 8, border: "1.5px solid #e2e8f0", cursor: "pointer", padding: 2 }} />
                    <input value={brand.secondary_color} onChange={e => setBrand(b => ({ ...b, secondary_color: e.target.value }))} style={{ ...inputStyle, flex: 1 }} />
                  </div>
                </div>
              </div>

              {/* Tone of voice */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Tone of Voice</label>
                <select value={brand.tone_of_voice} onChange={e => setBrand(b => ({ ...b, tone_of_voice: e.target.value }))} style={inputStyle}>
                  <option value="professional">Professional</option>
                  <option value="casual">Casual</option>
                  <option value="humorous">Humorous</option>
                  <option value="inspirational">Inspirational</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>

              {/* Target audience */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Target Audience</label>
                <textarea
                  value={brand.target_audience}
                  onChange={e => setBrand(b => ({ ...b, target_audience: e.target.value }))}
                  rows={3}
                  placeholder="Describe your ideal customer..."
                  style={{ ...inputStyle, resize: "none" }}
                />
              </div>

              {/* Industry */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Industry</label>
                <input value={brand.industry} onChange={e => setBrand(b => ({ ...b, industry: e.target.value }))} placeholder="e.g. SaaS, E-commerce, Healthcare..." style={inputStyle} />
              </div>

              {/* Competitors */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Competitors (comma-separated)</label>
                <input value={competitorsInput} onChange={e => setCompetitorsInput(e.target.value)} placeholder="Competitor A, Competitor B..." style={inputStyle} />
              </div>

              {/* Website URL */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Website URL</label>
                <input type="url" value={brand.website_url} onChange={e => setBrand(b => ({ ...b, website_url: e.target.value }))} placeholder="https://yoursite.com" style={inputStyle} />
              </div>

              {/* Logo description */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>Logo Description</label>
                <textarea
                  value={brand.logo_description}
                  onChange={e => setBrand(b => ({ ...b, logo_description: e.target.value }))}
                  rows={3}
                  placeholder="Describe your logo for AI image generation..."
                  style={{ ...inputStyle, resize: "none" }}
                />
              </div>
            </div>

            {/* Panel footer */}
            <div style={{ padding: "16px 24px", borderTop: "1px solid #e2e8f0", flexShrink: 0 }}>
              <button
                onClick={saveBrand}
                disabled={savingBrand}
                style={{ ...btnPrimary, width: "100%", padding: "12px", fontSize: 14 }}
              >
                {savingBrand ? <><Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} /> Saving...</> : brandSaved ? <><CheckCircle size={15} /> Saved!</> : "Save Brand Settings"}
                <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
              </button>
            </div>
          </div>
        </>
      )}

      <style jsx global>{`
        .marketing-scroll {
          scrollbar-width: thin;
          scrollbar-color: rgba(129, 140, 248, 0.55) rgba(255, 255, 255, 0.06);
        }
        .marketing-scroll::-webkit-scrollbar {
          width: 10px;
          height: 10px;
        }
        .marketing-scroll::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.04);
          border-radius: 999px;
        }
        .marketing-scroll::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, rgba(129, 140, 248, 0.85), rgba(99, 102, 241, 0.65));
          border-radius: 999px;
          border: 2px solid rgba(15, 23, 42, 0.35);
        }
        .marketing-scroll--soft::-webkit-scrollbar-track {
          background: rgba(15, 23, 42, 0.22);
        }
      `}</style>

    </div>
  );
}

export default function MarketingPage() {
  return (
    <ErrorBoundary>
      <MarketingPageInner />
    </ErrorBoundary>
  );
}
