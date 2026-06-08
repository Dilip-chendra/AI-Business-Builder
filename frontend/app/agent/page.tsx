"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, Globe, Zap, CheckCircle, XCircle, Loader2, ChevronDown, ChevronRight, AlertTriangle, Play, DollarSign, BookOpen, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { cleanDisplayText } from "@/lib/text";

type Step = { step: number; action: string; params: Record<string, unknown>; result: unknown; success: boolean; reason: string };
type RunResult = { run_id: string; goal: string; status: string; steps: Step[]; result: string | null; error: string | null; sources: string[]; cost_summary: Record<string, unknown>; started_at: string; finished_at: string | null };

const EXAMPLES = [
  "Create a lead follow-up playbook for a local HVAC business",
  "Generate SEO keyword ideas for emergency plumbing services",
  "Research competitor service offers for local roofing companies",
  "Summarize saved campaign reports into next-week sales tasks",
  "Find top 3 competitors pricing for AI SaaS tools",
];

const STATUS: Record<string, { bg: string; color: string; border: string; label: string }> = {
  done:           { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0", label: "Completed" },
  failed:         { bg: "#fef2f2", color: "#dc2626", border: "#fecaca", label: "Failed" },
  limit_exceeded: { bg: "#fffbeb", color: "#d97706", border: "#fde68a", label: "Limit Exceeded" },
  running:        { bg: "#eff6ff", color: "#2563eb", border: "#bfdbfe", label: "Running" },
};

const COST_ROWS: Array<[string, (s: Record<string, unknown>) => string]> = [
  ["Steps",       (s) => String(s.current_step ?? 0)],
  ["AI Requests", (s) => String(s.total_requests ?? 0)],
  ["Tokens",      (s) => String(s.total_tokens ?? 0)],
  ["Est. Cost",   (s) => "$" + Number(s.total_cost_usd || 0).toFixed(4)],
];

// ── Renders AI result text as formatted, human-readable content ──────────────
function ResultDisplay({ text, color }: { text: string; color: string }) {
  // Try to detect and parse JSON — render as cards instead of raw text
  const trimmed = text.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      return <JsonToCards data={parsed} />;
    } catch { /* not valid JSON, render as markdown */ }
  }

  // Render markdown-like text: ## headers, - bullets, **bold**
  const lines = cleanDisplayText(text).split("\n");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {lines.map((line, i) => {
        const trimLine = line.trim();
        if (!trimLine) return <div key={i} style={{ height: 6 }} />;

        // ## Header
        if (trimLine.startsWith("## ")) {
          return (
            <h3 key={i} style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", margin: "10px 0 4px", borderBottom: "1px solid #e2e8f0", paddingBottom: 4 }}>
              {trimLine.slice(3)}
            </h3>
          );
        }
        // # Header
        if (trimLine.startsWith("# ")) {
          return (
            <h2 key={i} style={{ fontSize: 17, fontWeight: 900, color: "#0f172a", margin: "12px 0 6px" }}>
              {trimLine.slice(2)}
            </h2>
          );
        }
        // Bullet point
        if (trimLine.startsWith("- ") || trimLine.startsWith("• ") || trimLine.startsWith("* ")) {
          const content = trimLine.slice(2);
          // Bold key: value pattern
          const boldMatch = content.match(/^\*\*(.+?)\*\*:?\s*(.*)/);
          return (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, marginTop: 9, flexShrink: 0 }} />
              <span style={{ fontSize: 14, color: "#1e293b", lineHeight: 1.6 }}>
                {boldMatch ? (
                  <><strong style={{ color: "#0f172a" }}>{boldMatch[1]}</strong>{boldMatch[2] ? `: ${boldMatch[2]}` : ""}</>
                ) : content}
              </span>
            </div>
          );
        }
        // Numbered list
        const numMatch = trimLine.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          return (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span style={{ background: color + "20", color, fontWeight: 800, fontSize: 12, width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
                {numMatch[1]}
              </span>
              <span style={{ fontSize: 14, color: "#1e293b", lineHeight: 1.6 }}>{numMatch[2]}</span>
            </div>
          );
        }
        // Plain paragraph
        return <p key={i} style={{ fontSize: 14, color: "#374151", lineHeight: 1.7, margin: 0 }}>{cleanDisplayText(trimLine)}</p>;
      })}
    </div>
  );
}

// ── Converts a JSON object/array into readable cards ─────────────────────────
function JsonToCards({ data }: { data: any }) {
  if (Array.isArray(data)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {data.map((item: any, i: number) => (
          <div key={i} style={{ background: "rgba(255,255,255,0.7)", borderRadius: 12, border: "1px solid rgba(0,0,0,0.08)", padding: "14px 16px" }}>
            {typeof item === "object" ? (
              Object.entries(item).map(([k, v]) => (
                <div key={k} style={{ display: "flex", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "capitalize", minWidth: 80 }}>
                    {k.replace(/_/g, " ")}
                  </span>
                  <span style={{ fontSize: 13, color: "#0f172a", fontWeight: 500 }}>
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </span>
                </div>
              ))
            ) : (
              <span style={{ fontSize: 14, color: "#0f172a" }}>{String(item)}</span>
            )}
          </div>
        ))}
      </div>
    );
  }
  if (typeof data === "object") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Object.entries(data).map(([k, v]) => (
          <div key={k} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-start" }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "capitalize", minWidth: 100 }}>
              {k.replace(/_/g, " ")}
            </span>
            <span style={{ fontSize: 13, color: "#0f172a" }}>
              {typeof v === "object" ? <JsonToCards data={v} /> : cleanDisplayText(v)}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return <p style={{ fontSize: 14, color: "#374151", margin: 0 }}>{String(data)}</p>;
}

export default function AgentPage() {
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"internal" | "browser">("internal");
  const [businessId, setBusinessId] = useState("");
  const [businesses, setBusinesses] = useState<{ id: string; name: string }[]>([]);
  const [applyActions, setApplyActions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listBusinesses()
      .then((l) => { setBusinesses(l.map((b) => ({ id: b.id, name: b.name }))); if (l[0]) setBusinessId(l[0].id); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (result && resultRef.current) resultRef.current.scrollIntoView({ behavior: "smooth" });
  }, [result]);

  async function runAgent(e: React.FormEvent) {
    e.preventDefault();
    if (!goal.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = mode === "browser"
        ? await api.runBrowserAgent({ goal: goal.trim(), business_id: businessId || undefined })
        : await api.runAgentController({ goal: goal.trim(), business_id: businessId || undefined, apply_actions: applyActions, use_browser: false, max_steps: 8 });
      setResult(r);
    } catch (err: any) {
      setError(err.message || "Agent run failed");
    } finally {
      setLoading(false);
    }
  }

  const toggleStep = (n: number) => setExpanded((p) => { const s = new Set(p); s.has(n) ? s.delete(n) : s.add(n); return s; });
  const st = result ? (STATUS[result.status] || STATUS.done) : null;

  return (
    <div className="anim-fade-in" style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Bot size={24} style={{ color: "#6366f1" }} /> Autonomous Agent
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Give the agent a goal. It plans, executes, and reports back using real AI.</p>
      </div>

      {/* Mode selector */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {([
          { id: "internal" as const, icon: Zap, label: "Internal Agent", desc: "Operates on your business data — analytics, products, copy" },
          { id: "browser" as const, icon: Globe, label: "Browser Research", desc: "Navigates real websites, extracts data, returns findings" },
        ]).map(({ id, icon: Icon, label, desc }) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            style={{
              display: "flex", alignItems: "flex-start", gap: 12,
              borderRadius: 16, border: `2px solid ${mode === id ? "#6366f1" : "#e2e8f0"}`,
              background: mode === id ? "#ede9fe" : "#fff",
              padding: "16px 18px", cursor: "pointer", textAlign: "left",
              transition: "all 0.15s", fontFamily: "inherit",
            }}
          >
            <div style={{ width: 38, height: 38, borderRadius: 10, background: mode === id ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Icon size={18} color={mode === id ? "#fff" : "#94a3b8"} />
            </div>
            <div>
              <p style={{ fontWeight: 700, fontSize: 14, color: mode === id ? "#4f46e5" : "#0f172a", margin: "0 0 3px" }}>{label}</p>
              <p style={{ fontSize: 12, color: "#94a3b8", margin: 0, lineHeight: 1.4 }}>{desc}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Form */}
      <form onSubmit={runAgent} style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "24px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: "#374151", display: "block", marginBottom: 8 }}>What do you want to achieve?</label>
          <textarea
            required
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. Find top 3 competitors pricing for AI SaaS tools"
            rows={3}
            style={{ width: "100%", borderRadius: 12, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "12px 14px", fontSize: 14, color: "#0f172a", outline: "none", resize: "none", fontFamily: "inherit", transition: "border-color 0.15s" }}
            onFocus={(e) => { e.target.style.borderColor = "#6366f1"; e.target.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; }}
            onBlur={(e) => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
          />
        </div>

        {/* Examples */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {EXAMPLES.map((eg) => (
            <button key={eg} type="button" onClick={() => setGoal(eg)}
              style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 99, padding: "5px 12px", fontSize: 11, fontWeight: 600, color: "#64748b", cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s" }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#6366f1"; e.currentTarget.style.color = "#6366f1"; e.currentTarget.style.background = "#ede9fe"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#e2e8f0"; e.currentTarget.style.color = "#64748b"; e.currentTarget.style.background = "#f8fafc"; }}
            >
              {eg}
            </button>
          ))}
        </div>

        {/* Business selector */}
        {businesses.length > 0 && (
          <div>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Business context (optional)</label>
            <select value={businessId} onChange={(e) => setBusinessId(e.target.value)}
              style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}>
              <option value="">No business context</option>
              {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        )}

        {/* Apply toggle */}
        {mode === "internal" && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, background: "#fffbeb", borderRadius: 12, border: "1px solid #fde68a", padding: "12px 14px" }}>
            <div
              onClick={() => setApplyActions(!applyActions)}
              style={{ width: 44, height: 24, borderRadius: 99, background: applyActions ? "#f59e0b" : "#e2e8f0", position: "relative", cursor: "pointer", transition: "background 0.2s", flexShrink: 0 }}
            >
              <div style={{ position: "absolute", top: 2, left: applyActions ? 22 : 2, width: 20, height: 20, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,0.2)", transition: "left 0.2s" }} />
            </div>
            <div>
              <p style={{ fontSize: 13, fontWeight: 700, color: "#92400e", margin: 0 }}>Allow agent to modify business data</p>
              {applyActions && <p style={{ fontSize: 11, color: "#b45309", margin: "2px 0 0" }}>⚠ Agent may update your business data</p>}
            </div>
          </div>
        )}

        {error && (
          <div style={{ display: "flex", gap: 8, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>
            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} /> {error}
          </div>
        )}

        <button type="submit" disabled={loading || !goal.trim()} className="btn-glow"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 800, fontSize: 15, padding: "14px", borderRadius: 14, border: "none", cursor: loading || !goal.trim() ? "not-allowed" : "pointer", opacity: loading || !goal.trim() ? 0.7 : 1, fontFamily: "inherit" }}>
          {loading ? <><Loader2 size={18} className="animate-spin" /> Agent running...</> : <><Play size={18} /> Run Agent</>}
        </button>

        {/* Loading progress hint */}
        {loading && (
          <div style={{ background: "#f8fafc", borderRadius: 12, border: "1px solid #e2e8f0", padding: "14px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <Loader2 size={14} className="animate-spin" style={{ color: "#6366f1" }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>
                {mode === "browser" ? "Browser agent is researching the web…" : "Agent is thinking and executing…"}
              </span>
            </div>
            <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>
              {mode === "browser"
                ? "Opening browser, navigating websites, extracting data. This takes 30–60 seconds."
                : "Analyzing your goal and generating a detailed response."}
            </p>
          </div>
        )}
      </form>

      {/* Results */}
      {result && st && (
        <div ref={resultRef} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Status */}
          <div style={{ borderRadius: 16, border: `1.5px solid ${st.border}`, background: st.bg, padding: "20px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: result.result ? 16 : 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 15, color: st.color }}>
                {result.status === "done" ? <CheckCircle size={18} /> : result.status === "running" ? <Loader2 size={18} className="animate-spin" /> : <XCircle size={18} />}
                {st.label}
              </div>
              <span style={{ fontSize: 11, color: "#94a3b8" }}>ID: {result.run_id.slice(0, 8)}…</span>
            </div>
            {result.result && <ResultDisplay text={result.result} color={st.color} />}
            {result.error && <p style={{ fontSize: 14, color: st.color, margin: 0, lineHeight: 1.6 }}>{result.error}</p>}
          </div>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", padding: "18px 20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 10px", display: "flex", alignItems: "center", gap: 6 }}>
                <Globe size={15} style={{ color: "#6366f1" }} /> Sources ({result.sources.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {result.sources.map((src, i) => (
                  <a key={i} href={src} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: "#6366f1", textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{src}</a>
                ))}
              </div>
            </div>
          )}

          {/* Steps */}
          <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", overflow: "hidden" }}>
            <div style={{ borderBottom: "1px solid #f1f5f9", padding: "16px 20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
                Execution Steps <span style={{ color: "#94a3b8", fontWeight: 500 }}>({result.steps.length})</span>
              </h3>
            </div>
            {result.steps.map((step) => (
              <div key={step.step} style={{ borderBottom: "1px solid #f8fafc" }}>
                <button onClick={() => toggleStep(step.step)}
                  style={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 20px", background: "none", border: "none", cursor: "pointer", textAlign: "left", fontFamily: "inherit" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {step.success
                      ? <CheckCircle size={15} style={{ color: "#10b981", flexShrink: 0 }} />
                      : <XCircle size={15} style={{ color: "#ef4444", flexShrink: 0 }} />}
                    <div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>
                        Step {step.step}: <code style={{ background: "#f1f5f9", padding: "1px 6px", borderRadius: 4, fontSize: 12 }}>{step.action}</code>
                      </span>
                      {step.reason && <p style={{ fontSize: 11, color: "#94a3b8", margin: "2px 0 0" }}>{step.reason}</p>}
                    </div>
                  </div>
                  {expanded.has(step.step)
                    ? <ChevronDown size={14} style={{ color: "#94a3b8", flexShrink: 0 }} />
                    : <ChevronRight size={14} style={{ color: "#94a3b8", flexShrink: 0 }} />}
                </button>
                {expanded.has(step.step) && (
                  <div style={{ padding: "0 20px 16px 44px", display: "flex", flexDirection: "column", gap: 10 }}>
                    {Object.keys(step.params).length > 0 && (
                      <div>
                        <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: "0 0 6px" }}>Params</p>
                        <pre style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "10px 12px", fontSize: 11, overflow: "auto", maxHeight: 120, margin: 0 }}>{JSON.stringify(step.params, null, 2)}</pre>
                      </div>
                    )}
                    {step.result != null && (
                      <div>
                        <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: "0 0 6px" }}>Result</p>
                        <pre style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "10px 12px", fontSize: 11, overflow: "auto", maxHeight: 160, margin: 0 }}>{typeof step.result === "string" ? step.result : JSON.stringify(step.result, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Cost summary */}
          {Object.keys(result.cost_summary).length > 0 && (
            <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", padding: "18px 20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 12px", display: "flex", alignItems: "center", gap: 6 }}>
                <DollarSign size={15} style={{ color: "#6366f1" }} /> Usage Summary
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                {COST_ROWS.map(([label, getValue]) => (
                  <div key={label} style={{ background: "#f8fafc", borderRadius: 10, border: "1px solid #e2e8f0", padding: "10px 12px" }}>
                    <p style={{ fontSize: 11, color: "#94a3b8", margin: "0 0 4px" }}>{label}</p>
                    <p style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>{getValue(result.cost_summary)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
