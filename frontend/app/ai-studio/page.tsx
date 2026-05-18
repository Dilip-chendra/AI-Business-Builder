"use client";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Send,
  Eye,
  RefreshCw,
  History,
  CheckCircle,
  Loader2,
  Bot,
  ChevronRight,
  Undo2,
  Rocket,
  Brain,
} from "lucide-react";
import { useActiveContext } from "@/lib/active-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Business {
  id: string;
  name: string;
}

interface VersionEntry {
  id: string;
  label: string;
  timestamp: string;
  prompt: string;
  snapshot: string;
}

interface DiffCard {
  field: string;
  before: string;
  after: string;
}

interface BrandContext {
  tone: string;
  audience: string;
  differentiators: string;
}

type GenerationStep = "Planning" | "Generating" | "Applying" | "Rendering" | "Complete";

const STEPS: GenerationStep[] = ["Planning", "Generating", "Applying", "Rendering", "Complete"];

const SUGGESTIONS = [
  "Make the hero section more compelling",
  "Add a testimonials section",
  "Improve the call-to-action buttons",
  "Update the colour scheme to feel more modern",
  "Add a pricing comparison table",
  "Optimise the page for mobile devices",
  "Add an FAQ section at the bottom",
];

// ─── GenerationProgress ───────────────────────────────────────────────────────

function GenerationProgress({ currentStep }: { currentStep: GenerationStep | null }) {
  if (!currentStep) return null;
  const currentIndex = STEPS.indexOf(currentStep);

  return (
    <div style={{ marginTop: 12, padding: "12px 14px", background: "#1e293b", borderRadius: 8, border: "1px solid #334155" }}>
      <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        Generation Progress
      </div>
      {STEPS.map((step, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        return (
          <div key={step} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{
              width: 18, height: 18, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
              background: done ? "#22c55e" : active ? "#6366f1" : "#334155",
              flexShrink: 0,
            }}>
              {done ? (
                <CheckCircle size={12} color="#fff" />
              ) : active ? (
                <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>
                  <Loader2 size={11} color="#fff" />
                </span>
              ) : (
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#475569", display: "block" }} />
              )}
            </div>
            <span style={{ fontSize: 13, color: done ? "#22c55e" : active ? "#a5b4fc" : "#64748b", fontWeight: active ? 600 : 400 }}>
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AIStudioPage() {
  const { businesses: contextBusinesses, active, setActiveContext, isLoading: contextLoading } = useActiveContext();
  const [selectedBusiness, setSelectedBusiness] = useState<string>("");
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState<GenerationStep | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [latestDiff, setLatestDiff] = useState<DiffCard | null>(null);
  const [brandContext, setBrandContext] = useState<BrandContext>({ tone: "", audience: "", differentiators: "" });
  const [brandOpen, setBrandOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  const businesses = contextBusinesses.map((item) => ({ id: item.id, name: item.name }));

  useEffect(() => {
    if (active.business_id) {
      setSelectedBusiness((current) => current || active.business_id || "");
      return;
    }
    if (businesses[0]) {
      setSelectedBusiness((current) => current || businesses[0].id);
    }
  }, [active.business_id, businesses]);

  // Load AI memory / brand context when business changes
  useEffect(() => {
    if (!selectedBusiness) return;
    const token = getToken();
    fetch(`${API_URL}/ai/memory/${selectedBusiness}`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data) {
          setBrandContext({
            tone: data.tone || "",
            audience: data.audience || "",
            differentiators: data.differentiators || "",
          });
        }
      })
      .catch(() => {});
    setPreviewUrl(`${typeof window !== "undefined" ? window.location.origin : "http://localhost:3000"}/landing/${selectedBusiness}?preview=1`);
    setPreviewKey((k) => k + 1);
  }, [selectedBusiness]);

  // Simulate generation steps
  async function runGenerationSteps() {
    for (const step of STEPS) {
      setGenerationStep(step);
      await new Promise((res) => setTimeout(res, step === "Complete" ? 400 : 900));
    }
    setGenerationStep(null);
  }

  async function handleSend() {
    if (!prompt.trim() || !selectedBusiness || isGenerating) return;
    setIsGenerating(true);

    const stepPromise = runGenerationSteps();

    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/agent/playground/modify`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          business_id: selectedBusiness,
          instruction: prompt,
          brand_context: brandContext,
        }),
      });

      await stepPromise;

      if (res.ok) {
        const data = await res.json();
        const newVersion: VersionEntry = {
          id: Date.now().toString(),
          label: prompt.slice(0, 48) + (prompt.length > 48 ? "..." : ""),
          timestamp: new Date().toLocaleTimeString(),
          prompt,
          snapshot: data.snapshot || "",
        };
        setVersions((v) => [newVersion, ...v]);

        if (data.diff) {
          setLatestDiff(data.diff);
        } else {
          setLatestDiff({ field: "Page content", before: "Previous version", after: "Updated by AI" });
        }

        setPreviewKey((k) => k + 1);
      }
    } catch {
      await stepPromise;
    } finally {
      setIsGenerating(false);
      setPrompt("");
    }
  }

  function handleUndo() {
    if (versions.length === 0) return;
    setVersions((v) => v.slice(1));
    setLatestDiff(null);
    setPreviewKey((k) => k + 1);
  }

  function handleSuggestion(s: string) {
    setPrompt(s);
    promptRef.current?.focus();
  }

  const selectedBusinessName = businesses.find((b) => b.id === selectedBusiness)?.name || "";

  if (!contextLoading && businesses.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "calc(100vh - 120px)", background: "#0f172a", borderRadius: 20, border: "1px solid #1e293b", padding: 24 }}>
        <div style={{ maxWidth: 560, textAlign: "center", padding: 28, borderRadius: 20, background: "#111827", border: "1px solid #1f2937" }}>
          <Sparkles size={34} color="#818cf8" style={{ margin: "0 auto 12px" }} />
          <h2 style={{ fontSize: 26, color: "#f8fafc", margin: "0 0 8px" }}>AI Studio needs a real business context</h2>
          <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.7, margin: "0 0 20px" }}>
            Generate your first business so AI Studio can work with real brand, landing page, and product data instead of placeholders.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
            <a href="/generator" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 18px", borderRadius: 12, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700, fontSize: 14 }}>
              <Sparkles size={14} />
              Generate Business
            </a>
            <a href="/dashboard" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 18px", borderRadius: 12, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>
              <Rocket size={14} />
              Go to Dashboard
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        * { box-sizing: border-box; }
        body { margin: 0; }
      `}</style>

      <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0f172a", color: "#e2e8f0", fontFamily: "system-ui, -apple-system, sans-serif" }}>

        {/* ── Top Bar ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 20px", height: 56, borderBottom: "1px solid #1e293b", flexShrink: 0, background: "#0f172a" }}>
          <Sparkles size={20} color="#818cf8" />
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.02em" }}>AI Studio</h1>

          <div style={{ flex: 1 }} />

          {/* Business selector */}
          <select
            value={selectedBusiness}
            onChange={(e) => {
              const next = e.target.value;
              setSelectedBusiness(next);
              setActiveContext({ business_id: next }).catch(console.error);
            }}
            style={{
              background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155",
              borderRadius: 6, padding: "6px 10px", fontSize: 13, cursor: "pointer", outline: "none",
            }}
          >
            {businesses.length === 0 && <option value="">No businesses</option>}
            {businesses.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>

          {/* Undo */}
          <button
            onClick={handleUndo}
            disabled={versions.length === 0}
            title="Undo last change"
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
              background: versions.length > 0 ? "#1e293b" : "#0f172a",
              border: "1px solid #334155", borderRadius: 6, color: versions.length > 0 ? "#e2e8f0" : "#475569",
              cursor: versions.length > 0 ? "pointer" : "not-allowed", fontSize: 13,
            }}
          >
            <Undo2 size={14} />
            Undo
          </button>

          {/* Deploy */}
          <a
            href={selectedBusiness ? `/deploy/${selectedBusiness}` : "#"}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
              background: "#4f46e5", borderRadius: 6, color: "#fff", textDecoration: "none",
              fontSize: 13, fontWeight: 600,
            }}
          >
            <Rocket size={14} />
            Deploy
          </a>
          <Link
            href="/ai-studio/version-history"
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
              background: "#1e293b", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0", textDecoration: "none",
              fontSize: 13, fontWeight: 600,
            }}
          >
            <History size={14} />
            View Version History
          </Link>
        </div>

        {/* ── Three-column body ── */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

          {/* ── Left Panel ── */}
          <div style={{ width: 320, flexShrink: 0, borderRight: "1px solid #1e293b", display: "flex", flexDirection: "column", overflow: "hidden", background: "#0f172a" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>

              {/* Prompt area */}
              <div style={{ marginBottom: 12 }}>
                <textarea
                  ref={promptRef}
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(); }}
                  placeholder="Describe what you want to change..."
                  style={{
                    width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155",
                    borderRadius: 8, padding: "10px 12px", fontSize: 13, resize: "vertical", outline: "none",
                    lineHeight: 1.5,
                  }}
                />
                <button
                  onClick={handleSend}
                  disabled={isGenerating || !prompt.trim() || !selectedBusiness}
                  style={{
                    marginTop: 8, width: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                    gap: 8, padding: "9px 0", background: isGenerating ? "#312e81" : "#4f46e5",
                    border: "none", borderRadius: 8, color: "#fff", fontSize: 14, fontWeight: 600,
                    cursor: isGenerating || !prompt.trim() || !selectedBusiness ? "not-allowed" : "pointer",
                    opacity: !prompt.trim() || !selectedBusiness ? 0.5 : 1,
                  }}
                >
                  {isGenerating ? (
                    <>
                      <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}><Loader2 size={15} /></span>
                      Generating...
                    </>
                  ) : (
                    <>
                      <Send size={15} />
                      Send
                    </>
                  )}
                </button>
              </div>

              {/* Generation progress */}
              <GenerationProgress currentStep={generationStep} />

              {/* Suggestion chips */}
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 8 }}>
                  Suggestions
                </div>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSuggestion(s)}
                    style={{
                      display: "flex", alignItems: "center", gap: 6, width: "100%", textAlign: "left",
                      background: "transparent", border: "1px solid #1e293b", borderRadius: 6,
                      color: "#94a3b8", fontSize: 12, padding: "7px 10px", marginBottom: 6,
                      cursor: "pointer", transition: "border-color 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#4f46e5")}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#1e293b")}
                  >
                    <ChevronRight size={12} color="#4f46e5" />
                    {s}
                  </button>
                ))}
              </div>

              {/* Conversation History */}
              {versions.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 12 }}>
                    Conversation History
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {versions.slice(0, 5).map((v) => (
                      <div key={v.id} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {/* User Bubble */}
                        <div style={{ display: "flex", gap: 8, alignSelf: "flex-end", maxWidth: "85%" }}>
                          <div style={{ background: "#4f46e5", color: "#fff", padding: "8px 12px", borderRadius: "12px 12px 0 12px", fontSize: 13, lineHeight: 1.4 }}>
                            {v.prompt}
                          </div>
                        </div>
                        {/* AI Bubble */}
                        <div style={{ display: "flex", gap: 8, alignSelf: "flex-start", maxWidth: "85%" }}>
                          <div style={{ width: 24, height: 24, borderRadius: "50%", background: "#1e293b", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                            <Bot size={14} color="#818cf8" />
                          </div>
                          <div style={{ background: "#1e293b", color: "#e2e8f0", padding: "8px 12px", borderRadius: "12px 12px 12px 0", fontSize: 13, lineHeight: 1.4, border: "1px solid #334155" }}>
                            I've updated the landing page based on your instructions.
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Brand Context collapsible */}
              <div style={{ marginTop: 16, border: "1px solid #1e293b", borderRadius: 8, overflow: "hidden" }}>
                <button
                  onClick={() => setBrandOpen((o) => !o)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    width: "100%", padding: "10px 12px", background: "#1e293b",
                    border: "none", color: "#e2e8f0", fontSize: 13, fontWeight: 600, cursor: "pointer",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Brain size={14} color="#818cf8" />
                    Brand Context
                  </span>
                  <span style={{ transform: brandOpen ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s", display: "inline-block" }}>
                    <ChevronRight size={14} color="#64748b" />
                  </span>
                </button>
                {brandOpen && (
                  <div style={{ padding: 12, background: "#0f172a" }}>
                    {(["tone", "audience", "differentiators"] as const).map((field) => (
                      <div key={field} style={{ marginBottom: 10 }}>
                        <label style={{ display: "block", fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "capitalize", marginBottom: 4 }}>
                          {field}
                        </label>
                        <input
                          type="text"
                          value={brandContext[field]}
                          onChange={(e) => setBrandContext((bc) => ({ ...bc, [field]: e.target.value }))}
                          placeholder={field === "tone" ? "e.g. professional, friendly" : field === "audience" ? "e.g. small business owners" : "e.g. fast delivery, local focus"}
                          style={{
                            width: "100%", background: "#1e293b", color: "#e2e8f0",
                            border: "1px solid #334155", borderRadius: 6, padding: "6px 10px",
                            fontSize: 12, outline: "none",
                          }}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
          </div>

          {/* ── Centre Panel ── */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "#020617" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 16px", borderBottom: "1px solid #1e293b", flexShrink: 0 }}>
              <Eye size={14} color="#64748b" />
              <span style={{ fontSize: 13, color: "#64748b" }}>
                {selectedBusinessName ? `Preview: ${selectedBusinessName}` : "Preview"}
              </span>
              <div style={{ flex: 1 }} />
              <button
                onClick={() => setPreviewKey((k) => k + 1)}
                title="Refresh preview"
                style={{ background: "transparent", border: "none", color: "#64748b", cursor: "pointer", display: "flex", alignItems: "center" }}
              >
                <RefreshCw size={14} />
              </button>
            </div>

            <div style={{ flex: 1, position: "relative" }}>
              {!selectedBusiness ? (
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
                  <Bot size={48} color="#1e293b" />
                  <p style={{ color: "#475569", fontSize: 14, margin: 0 }}>Select a business to preview</p>
                </div>
              ) : (
                <iframe
                  key={previewKey}
                  src={previewUrl ? `${previewUrl}${previewUrl.includes("?") ? "&" : "?"}v=${previewKey}` : previewUrl}
                  style={{ width: "100%", height: "100%", border: "none", background: "#fff" }}
                  title="Business preview"
                />
              )}
            </div>
          </div>

          {/* ── Right Panel ── */}
          <div style={{ width: 280, flexShrink: 0, borderLeft: "1px solid #1e293b", display: "flex", flexDirection: "column", overflow: "hidden", background: "#0f172a" }}>
            <div style={{ padding: "12px 16px", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              <History size={14} color="#818cf8" />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0" }}>Studio Timeline</span>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ padding: 14, background: "linear-gradient(180deg,#1e1b4b,#111827)", borderRadius: 14, border: "1px solid #312e81" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
                  <div>
                    <p style={{ fontSize: 11, color: "#a5b4fc", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", margin: 0 }}>Version History</p>
                    <h3 style={{ fontSize: 15, color: "#f8fafc", margin: "6px 0 0", fontWeight: 800 }}>Dedicated history workspace</h3>
                  </div>
                  <span style={{ fontSize: 11, color: "#c7d2fe", background: "rgba(99,102,241,0.18)", borderRadius: 999, padding: "4px 8px", fontWeight: 700 }}>
                    {versions.length} local changes
                  </span>
                </div>
                <p style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.7, margin: 0 }}>
                  Open the full history view to compare prompts, preview outputs, restore earlier versions, or clean up drafts without crowding the main studio.
                </p>
                <Link
                  href="/ai-studio/version-history"
                  style={{
                    marginTop: 14,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "9px 12px",
                    background: "#6366f1",
                    borderRadius: 10,
                    color: "#fff",
                    textDecoration: "none",
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                >
                  <History size={14} />
                  Open Version History
                </Link>
              </div>

              {latestDiff ? (
                <div style={{ padding: 12, background: "#1e293b", borderRadius: 12, border: "1px solid #334155" }}>
                  <div style={{ fontSize: 11, color: "#818cf8", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>
                    Latest Change
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6 }}>
                    <span style={{ color: "#64748b" }}>Field:</span> {latestDiff.field}
                  </div>
                  <div style={{ fontSize: 12, color: "#fca5a5", marginBottom: 6, lineHeight: 1.6 }}>
                    Before: {latestDiff.before}
                  </div>
                  <div style={{ fontSize: 12, color: "#86efac", lineHeight: 1.6 }}>
                    After: {latestDiff.after}
                  </div>
                </div>
              ) : (
                <div style={{ padding: 14, background: "#111827", borderRadius: 12, border: "1px solid #1f2937" }}>
                  <p style={{ fontSize: 13, color: "#94a3b8", margin: 0, lineHeight: 1.7 }}>
                    The latest change summary will appear here after AI Studio applies your next prompt.
                  </p>
                </div>
              )}

              <div style={{ padding: 14, background: "#111827", borderRadius: 12, border: "1px solid #1f2937" }}>
                <p style={{ fontSize: 11, color: "#64748b", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", margin: "0 0 8px" }}>
                  Recent prompts
                </p>
                {versions.length === 0 ? (
                  <p style={{ color: "#475569", fontSize: 13, margin: 0 }}>No versions yet. Send a prompt to start building the timeline.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {versions.slice(0, 3).map((version) => (
                      <div key={version.id} style={{ borderRadius: 10, border: "1px solid #243041", padding: "10px 12px", background: "#0f172a" }}>
                        <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {version.label}
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b" }}>{version.timestamp}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
