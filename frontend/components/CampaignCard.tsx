"use client";

import { useState } from "react";
import { CheckCircle, XCircle, Loader2, Sparkles } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function EmailPreview({ content }: { content: Record<string, any> }) {
  const [tab, setTab] = useState<"preview" | "html" | "text">("preview");
  const html = content.html || content.html_body || "";
  const text = content.plain_text || content.plain_text_body || content.body || "";
  const subject = content.subject || "";
  const preview = content.preview_text || "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {subject && (
        <div style={{ background: "#f8fafc", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>Subject</p>
          <p style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", margin: 0 }}>{subject}</p>
        </div>
      )}
      {preview && <p style={{ fontSize: 12, color: "#64748b", margin: 0, fontStyle: "italic" }}>Preview: {preview}</p>}
      <div style={{ display: "flex", gap: 4, background: "#f1f5f9", borderRadius: 10, padding: 3 }}>
        {(["preview", "html", "text"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ flex: 1, borderRadius: 8, padding: "5px 8px", fontSize: 11, fontWeight: 700, border: "none", cursor: "pointer", fontFamily: "inherit", background: tab === t ? "#fff" : "transparent", color: tab === t ? "#0f172a" : "#94a3b8", boxShadow: tab === t ? "0 1px 3px rgba(0,0,0,0.08)" : "none", textTransform: "capitalize" }}>
            {t}
          </button>
        ))}
      </div>
      {tab === "preview" && html && (
        <div style={{ borderRadius: 10, overflow: "hidden", border: "1px solid #e2e8f0", height: 300 }}>
          <iframe srcDoc={html} style={{ width: "100%", height: "100%", border: "none" }} title="Email preview" sandbox="allow-same-origin" />
        </div>
      )}
      {tab === "html" && (
        <pre style={{ background: "#0f172a", color: "#a5b4fc", borderRadius: 10, padding: "12px", fontSize: 10, overflow: "auto", maxHeight: 300, margin: 0 }}>
          {html.slice(0, 2000)}{html.length > 2000 ? "…" : ""}
        </pre>
      )}
      {tab === "text" && (
        <pre style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "12px", fontSize: 12, overflow: "auto", maxHeight: 200, margin: 0, whiteSpace: "pre-wrap" }}>
          {text.slice(0, 1000)}
        </pre>
      )}
    </div>
  );
}

export function CampaignContent({ campaign }: { campaign: { campaign_type: string; content: Record<string, any> } }) {
  const c = campaign.content;
  if (!c || Object.keys(c).length === 0) return <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>No content yet.</p>;

  if (campaign.campaign_type === "email") return <EmailPreview content={c} />;

  if (campaign.campaign_type === "social") {
    const posts = c.posts || [];
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>Platform: {c.platform}</p>
        {posts.slice(0, 3).map((post: any, i: number) => (
          <div key={i} style={{ background: "#f8fafc", borderRadius: 10, padding: "10px 12px", borderLeft: "3px solid #7c3aed" }}>
            <p style={{ fontSize: 13, color: "#0f172a", lineHeight: 1.6, margin: "0 0 6px" }}>{post.text}</p>
            {post.hashtags?.length > 0 && (
              <p style={{ fontSize: 11, color: "#7c3aed", margin: 0, fontWeight: 600 }}>
                {post.hashtags.slice(0, 4).map((h: string) => `#${h}`).join(" ")}
              </p>
            )}
          </div>
        ))}
        {posts.length > 3 && <p style={{ fontSize: 11, color: "#94a3b8", margin: 0 }}>+{posts.length - 3} more posts</p>}
      </div>
    );
  }

  // Ads
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {c.campaign_name && (
        <div style={{ background: "#fef3c7", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#92400e", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>Campaign</p>
          <p style={{ fontSize: 14, fontWeight: 700, color: "#92400e", margin: 0 }}>{c.campaign_name}</p>
        </div>
      )}
      {c.ad_creatives?.slice(0, 2).map((ad: any, i: number) => (
        <div key={i} style={{ background: "#f8fafc", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>{ad.headline}</p>
          <p style={{ fontSize: 12, color: "#64748b", margin: "0 0 4px" }}>{ad.description}</p>
          {ad.cta && <span style={{ fontSize: 11, fontWeight: 700, color: "#d97706", background: "#fef3c7", padding: "2px 8px", borderRadius: 99 }}>{ad.cta}</span>}
        </div>
      ))}
      {c.estimated_reach && <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>Est. reach: <strong>{c.estimated_reach?.toLocaleString()}</strong></p>}
    </div>
  );
}

export function MetricBadge({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", background: `${color}12`, borderRadius: 8, padding: "6px 10px", minWidth: 60 }}>
      <span style={{ fontSize: 15, fontWeight: 900, color }}>{value}</span>
      <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
    </div>
  );
}
