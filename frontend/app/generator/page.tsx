"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles, AlertTriangle, ExternalLink, Zap, Target,
  Users, TrendingUp, ArrowRight, CheckCircle, Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useActiveContext } from "@/lib/active-context";
import { useAsync } from "@/hooks/useAsync";

const EXAMPLES = [
  { label: "HVAC Growth OS", interests: "HVAC maintenance, local service operations, customer follow-up", niche: "Residential HVAC services", audience: "Homeowners within a 20-mile service area", goals: "Book more tune-up calls and track real service revenue" },
  { label: "Plumbing Leads", interests: "Emergency plumbing, local SEO, fast lead response", niche: "Residential plumbing services", audience: "Homeowners with urgent repair needs", goals: "Generate quote requests and same-day booking calls" },
  { label: "Roofing Inspections", interests: "Roof inspections, storm season campaigns, review generation", niche: "Residential roofing services", audience: "Homeowners after storms or with aging roofs", goals: "Book inspection appointments and follow up automatically" },
  { label: "AI Productivity", interests: "AI productivity tools", niche: "B2B SaaS", audience: "Remote workers", goals: "Generate passive income" },
  { label: "Fitness Coaching", interests: "Fitness coaching", niche: "Health & wellness", audience: "Busy professionals", goals: "Build an audience" },
];

const STEPS = [
  { icon: Zap, label: "Market Fit", desc: "Anchors to a real buyer pain" },
  { icon: Target, label: "Growth System", desc: "Builds offer and workflows" },
  { icon: TrendingUp, label: "Launch Assets", desc: "Creates page and campaigns" },
];

const INPUT_FIELDS = [
  { key: "interests", label: "Your interests / skills", icon: Zap, placeholder: "e.g. HVAC maintenance, plumbing repair, local service marketing", required: true, color: "#6366f1" },
  { key: "niche_preferences", label: "Niche preferences", icon: Target, placeholder: "e.g. residential HVAC, plumbing, electrical, roofing, local services", required: false, color: "#8b5cf6" },
  { key: "target_audience", label: "Target audience", icon: Users, placeholder: "e.g. homeowners within 20 miles, property managers, local families", required: false, color: "#06b6d4" },
  { key: "goals", label: "Business goals", icon: TrendingUp, placeholder: "e.g. book service calls, speed up follow-up, track booked revenue", required: false, color: "#10b981" },
] as const;

export default function GeneratorPage() {
  const router = useRouter();
  const { setActiveContext, refresh } = useActiveContext();
  const [form, setForm] = useState({ interests: "", niche_preferences: "", target_audience: "", goals: "" });
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const { run, loading, error } = useAsync(api.generateBusiness);

  const isAIUnavailable = error?.includes("503") || error?.includes("No AI provider") || error?.includes("SERVICE_UNAVAILABLE");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const business = await run(form);
      await setActiveContext({
        workspace_id: business.workspace_id || null,
        business_id: business.id,
        project_id: business.project_id || null,
      });
      await refresh();
      router.push(`/dashboard?created_business=${business.id}`);
    } catch { /* captured by useAsync */ }
  }

  return (
    <div className="anim-fade-in" style={{ maxWidth: 760, margin: "0 auto" }}>

      {/* ── Header ──────────────────────────────────── */}
      <div style={{ textAlign: "center", marginBottom: 36 }}>
        <div
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: "rgba(99,102,241,0.1)", color: "#6366f1",
            borderRadius: 99, padding: "6px 14px", fontSize: 13, fontWeight: 600,
            marginBottom: 16,
          }}
        >
          <Sparkles size={14} />
          AI Business Generator
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 900, color: "#0f172a", margin: "0 0 10px", lineHeight: 1.2 }}>
          Turn your idea into a{" "}
          <span style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            real business
          </span>
        </h1>
        <p style={{ fontSize: 15, color: "#64748b", margin: 0, lineHeight: 1.6 }}>
          Describe what you want to build. AI generates a strategy, landing page, and launch plan grounded in real execution workflows.
        </p>
      </div>

      <div style={{ marginBottom: 24, borderRadius: 20, border: "1px solid #bae6fd", background: "linear-gradient(135deg,#f0f9ff,#eef2ff)", padding: 18 }}>
        <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 900, color: "#0369a1", letterSpacing: "0.1em", textTransform: "uppercase" }}>Report-backed recommendation</p>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "#0f172a", fontWeight: 700 }}>
          The strongest starting market is local home services: HVAC, plumbing, electrical, and roofing teams that need faster lead response, appointment booking, review requests, and revenue attribution.
        </p>
      </div>

      {/* ── How it works ────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 28 }}>
        {STEPS.map(({ icon: Icon, label, desc }, i) => (
          <div
            key={label}
            style={{
              background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
              padding: "16px 14px", textAlign: "center", position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)",
                width: 22, height: 22, borderRadius: "50%",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: "#fff", fontSize: 11, fontWeight: 800,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {i + 1}
            </div>
            <div
              style={{
                width: 38, height: 38, borderRadius: 10, margin: "8px auto 10px",
                background: "rgba(99,102,241,0.1)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <Icon size={18} style={{ color: "#6366f1" }} />
            </div>
            <p style={{ fontWeight: 700, fontSize: 13, color: "#0f172a", margin: "0 0 3px" }}>{label}</p>
            <p style={{ fontSize: 11, color: "#94a3b8", margin: 0 }}>{desc}</p>
          </div>
        ))}
      </div>

      {/* ── Quick examples ───────────────────────────── */}
      <div style={{ marginBottom: 20 }}>
        <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", marginBottom: 8 }}>
          Quick start
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => setForm({ interests: ex.interests, niche_preferences: ex.niche, target_audience: ex.audience, goals: ex.goals })}
              style={{
                background: "#fff", border: "1px solid #e2e8f0", borderRadius: 99,
                padding: "6px 14px", fontSize: 12, fontWeight: 600, color: "#64748b",
                cursor: "pointer", transition: "all 0.15s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#6366f1"; e.currentTarget.style.color = "#6366f1"; e.currentTarget.style.background = "#ede9fe"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#e2e8f0"; e.currentTarget.style.color = "#64748b"; e.currentTarget.style.background = "#fff"; }}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Form ────────────────────────────────────── */}
      <form
        onSubmit={submit}
        style={{
          background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0",
          padding: "28px 28px", boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {INPUT_FIELDS.map(({ key, label, icon: Icon, placeholder, required, color }) => (
            <div key={key} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 700, color: "#374151" }}>
                <Icon size={13} style={{ color }} />
                {label} {required && <span style={{ color: "#ef4444" }}>*</span>}
              </label>
              <textarea
                required={required}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                onFocus={() => setFocusedField(key)}
                onBlur={() => setFocusedField(null)}
                placeholder={placeholder}
                rows={3}
                style={{
                  width: "100%", borderRadius: 12, resize: "none",
                  border: `1.5px solid ${focusedField === key ? color : "#e2e8f0"}`,
                  background: focusedField === key ? "#fafafa" : "#f8fafc",
                  padding: "10px 12px", fontSize: 13, color: "#0f172a",
                  outline: "none", transition: "all 0.15s",
                  boxShadow: focusedField === key ? `0 0 0 3px ${color}18` : "none",
                  fontFamily: "inherit",
                }}
              />
            </div>
          ))}
        </div>

        {/* AI unavailable */}
        {isAIUnavailable && (
          <div
            style={{
              marginTop: 16, borderRadius: 12, border: "1px solid #fde68a",
              background: "#fffbeb", padding: "14px 16px",
              display: "flex", gap: 12,
            }}
          >
            <AlertTriangle size={18} style={{ color: "#d97706", flexShrink: 0, marginTop: 1 }} />
            <div>
              <p style={{ fontWeight: 700, color: "#92400e", fontSize: 13, margin: "0 0 4px" }}>No AI provider available</p>
              <p style={{ fontSize: 12, color: "#b45309", margin: "0 0 8px" }}>
                Configure one in <code style={{ background: "#fef3c7", padding: "1px 4px", borderRadius: 4 }}>backend/.env</code>:
              </p>
              <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 12, color: "#b45309", lineHeight: 1.8 }}>
                <li><strong>Groq</strong> (free, fastest) — set <code style={{ background: "#fef3c7", padding: "1px 4px", borderRadius: 4 }}>GROQ_API_KEY</code></li>
                <li><strong>Ollama</strong> (local) — run <code style={{ background: "#fef3c7", padding: "1px 4px", borderRadius: 4 }}>ollama pull llama3</code></li>
              </ul>
              <Link href="/ai-status" style={{ display: "inline-flex", alignItems: "center", gap: 4, marginTop: 8, fontSize: 12, fontWeight: 600, color: "#d97706", textDecoration: "none" }}>
                Check AI status <ExternalLink size={11} />
              </Link>
            </div>
          </div>
        )}

        {error && !isAIUnavailable && (
          <div style={{ marginTop: 16, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="btn-glow"
          style={{
            marginTop: 20, width: "100%",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            background: loading ? "#a5b4fc" : "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "#fff", fontWeight: 800, fontSize: 16,
            padding: "15px 24px", borderRadius: 14, border: "none",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "all 0.2s",
          }}
        >
          {loading ? (
            <>
              <Loader2 size={20} className="animate-spin" />
              Generating your business...
            </>
          ) : (
            <>
              <Sparkles size={20} />
              Generate My Business
              <ArrowRight size={18} />
            </>
          )}
        </button>

        {/* Loading progress */}
        {loading && (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
            {["Analyzing market trends...", "Building business strategy...", "Creating landing page copy..."].map((step, i) => (
              <div key={step} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#94a3b8" }}>
                {i === 0 ? (
                  <CheckCircle size={13} style={{ color: "#10b981" }} />
                ) : (
                  <div style={{ width: 13, height: 13, borderRadius: "50%", border: "1.5px solid #e2e8f0", borderTopColor: "#6366f1", animation: "spin 1s linear infinite" }} />
                )}
                {step}
              </div>
            ))}
          </div>
        )}
      </form>

      <p style={{ textAlign: "center", fontSize: 12, color: "#94a3b8", marginTop: 14 }}>
        Powered by real AI — Groq, HuggingFace, or Ollama. No fake data.{" "}
        <Link href="/ai-status" style={{ color: "#6366f1", textDecoration: "none", fontWeight: 600 }}>Check provider status</Link>
      </p>
    </div>
  );
}
