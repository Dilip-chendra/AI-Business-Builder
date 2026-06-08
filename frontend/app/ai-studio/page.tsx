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

interface PreviewSnapshot {
  headline?: string;
  subheading?: string;
  cta_text?: string;
  page_content?: {
    color_scheme?: string;
    urgency_text?: string;
    trust_badges?: string[];
    [key: string]: unknown;
  };
}

interface VersionEntry {
  id: string;
  label: string;
  timestamp: string;
  prompt: string;
  snapshot: string;
  summary?: string;
  versionId?: string;
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

interface StudioMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: string;
  action_type?: string | null;
  metadata?: {
    version_id?: string;
    version_number?: number;
    diff?: DiffCard;
    field?: string;
    old_value?: unknown;
    new_value?: unknown;
    updated_files?: string[];
    error?: string;
    [key: string]: unknown;
  };
  created_at?: string | null;
}

interface StudioActionResult {
  action_type?: string;
  summary?: string;
  next_url?: string;
  file_path?: string;
  changed_files?: string[];
  updated_files?: string[];
  campaign_name?: string;
  report_id?: string;
  product_id?: string;
  provider_used?: string;
  preview_url?: string;
  orchestration?: OrchestrationTrace;
}

interface OrchestrationStep {
  label?: string;
  status?: string;
  detail?: string;
  timestamp?: string;
}

interface OrchestrationTrace {
  instruction?: string;
  intent?: string;
  selected_tool?: string;
  tool_label?: string;
  reason?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  action_type?: string;
  updated_files?: string[];
  provider_used?: string;
  version_id?: string | null;
  next_url?: string;
  error?: string;
  persisted_targets?: string[];
  steps?: OrchestrationStep[];
}

interface TimelineAction {
  id: string;
  prompt: string;
  response: string;
  status: string;
  action_type?: string | null;
  timestamp: string;
  trace?: OrchestrationTrace;
}

type GenerationStep = "Planning" | "Applying" | "Persisting" | "Rendering" | "Complete";

const STEPS: GenerationStep[] = ["Planning", "Applying", "Persisting", "Rendering", "Complete"];

function formatLocalTime(value?: string | null): string {
  if (!value) return "";
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

function asOrchestrationTrace(value: unknown): OrchestrationTrace | undefined {
  if (!value || typeof value !== "object") return undefined;
  return value as OrchestrationTrace;
}

function formatDuration(ms?: number): string {
  if (typeof ms !== "number" || Number.isNaN(ms)) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const SUGGESTIONS = [
  "Reposition this page around booked service calls and fast follow-up",
  "Add a local trust section with reviews, service area, and emergency response",
  "Make the hero speak to homeowners who need HVAC, plumbing, electrical, or roofing help",
  "Add lead capture and quote request sections below the hero",
  "Improve the call-to-action buttons for appointment booking",
  "Add proof that campaign metrics are tracked from real events",
  "Add an FAQ section about pricing, response time, and service guarantees",
];

// ─── GenerationProgress ───────────────────────────────────────────────────────

function GenerationProgress({ currentStep }: { currentStep: GenerationStep | null }) {
  if (!currentStep) return null;
  const currentIndex = STEPS.indexOf(currentStep);

  return (
    <div style={{ marginTop: 12, padding: "12px 14px", background: "#1e293b", borderRadius: 8, border: "1px solid #334155" }}>
      <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        Execution Progress
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
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [latestDiff, setLatestDiff] = useState<DiffCard | null>(null);
  const [brandContext, setBrandContext] = useState<BrandContext>({ tone: "", audience: "", differentiators: "" });
  const [brandOpen, setBrandOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [studioError, setStudioError] = useState<string>("");
  const [appliedNotice, setAppliedNotice] = useState<string>("");
  const [previewSnapshot, setPreviewSnapshot] = useState<PreviewSnapshot | null>(null);
  const [latestAction, setLatestAction] = useState<StudioActionResult | null>(null);
  const [latestTrace, setLatestTrace] = useState<OrchestrationTrace | null>(null);
  const [timelineActions, setTimelineActions] = useState<TimelineAction[]>([]);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  const businesses = contextBusinesses.map((item) => ({ id: item.id, name: item.name }));
  const selectedBusinessRecord = contextBusinesses.find((item) => item.id === selectedBusiness) || null;

  useEffect(() => {
    if (!appliedNotice) return;
    const timer = window.setTimeout(() => setAppliedNotice(""), 1000);
    return () => window.clearTimeout(timer);
  }, [appliedNotice]);

  function syncTimeline(nextMessages: StudioMessage[]) {
    setMessages(nextMessages);
    const pairedActions: TimelineAction[] = [];
    let pendingUser: StudioMessage | null = null;
    for (const message of nextMessages) {
      if (message.role === "user") {
        pendingUser = message;
        continue;
      }
      if (message.role !== "assistant") continue;
      const trace = asOrchestrationTrace(message.metadata?.orchestration);
      pairedActions.push({
        id: message.id,
        prompt: trace?.instruction || pendingUser?.content || "Prompt was not recorded",
        response: message.content,
        status: message.status,
        action_type: message.action_type,
        timestamp: formatLocalTime(message.created_at),
        trace,
      });
    }
    const newestActions = pairedActions.slice().reverse();
    setTimelineActions(newestActions);
    const newestTrace = newestActions.find((item) => item.trace)?.trace;
    if (newestTrace) {
      setLatestTrace(newestTrace);
    } else if (nextMessages.length === 0) {
      setLatestTrace(null);
    }
    const assistantActions = nextMessages.filter((message) => message.role === "assistant" && message.metadata?.version_id);
    setVersions(assistantActions.slice().reverse().map((message) => {
      const previousUser = [...nextMessages]
        .reverse()
        .find((candidate) => candidate.role === "user" && new Date(candidate.created_at || 0) <= new Date(message.created_at || 0));
      return {
        id: message.id,
        versionId: String(message.metadata?.version_id || ""),
        label: (previousUser?.content || message.content).slice(0, 48) + ((previousUser?.content || message.content).length > 48 ? "..." : ""),
        timestamp: formatLocalTime(message.created_at),
        prompt: previousUser?.content || "",
        snapshot: "",
        summary: message.content,
      };
    }));
    const latestAction = [...assistantActions].reverse()[0];
    const diff = latestAction?.metadata?.diff;
    if (diff && typeof diff.field === "string") {
      setLatestDiff(diff);
    } else if (!latestAction) {
      setLatestDiff(null);
    }
  }

  function studioSafeError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error || "");
    const lower = raw.toLowerCase();
    if (!raw.trim()) return "AI Studio request failed. Please try again.";
    if (lower.includes("could not parse json") || lower.includes("unterminated string") || lower.includes("structured change plan")) {
      return "The AI provider returned an incomplete structured edit. AI Studio did not apply a broken change. Please retry the prompt; the backend will request a repaired structured plan.";
    }
    if (lower.includes("timed out") || lower.includes("timeout")) {
      return "The AI provider took too long to respond. Please retry; larger page changes can take up to a few minutes.";
    }
    if (lower.includes("no ai provider") || lower.includes("provider failed") || lower.includes("api_key")) {
      return "AI Studio could not reach a working AI provider. Check the Provider Audit page or backend .env, then retry.";
    }
    return raw.length > 220 ? `${raw.slice(0, 220)}...` : raw;
  }

  async function loadTimeline(businessId: string) {
    const token = getToken();
    const res = await fetch(`${API_URL}/ai-studio/${businessId}/timeline`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      cache: "no-store",
    });
    if (!res.ok) return;
    const data = await res.json();
    syncTimeline(data.messages || []);
  }

  async function loadPreviewSnapshot(businessId: string, freshKey = Date.now()) {
    const res = await fetch(`${API_URL}/businesses/${businessId}/landing-page-preview?fresh=${freshKey}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    const snapshot: PreviewSnapshot = {
      headline: data.headline,
      subheading: data.subheading,
      cta_text: data.cta_text,
      page_content: data.page_content || {},
    };
    setPreviewSnapshot(snapshot);
    return snapshot;
  }

  useEffect(() => {
    if (active.business_id) {
      setSelectedBusiness(active.business_id);
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
    setStudioError("");
    fetch(`${API_URL}/ai/memory/${selectedBusiness}`, {
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data) {
          setBrandContext({
            tone: data.tone_of_voice || "",
            audience: data.target_audience || "",
            differentiators: Array.isArray(data.key_differentiators)
              ? data.key_differentiators.join(", ")
              : data.key_differentiators || "",
          });
        }
      })
      .catch(() => {});
    loadTimeline(selectedBusiness).catch(() => {});
    loadPreviewSnapshot(selectedBusiness).catch(() => {});
    setPreviewUrl(`${typeof window !== "undefined" ? window.location.origin : "http://localhost:3000"}/landing/${selectedBusiness}?preview=1`);
    setPreviewKey((k) => k + 1);
  }, [selectedBusiness]);

  async function handleSend() {
    if (!prompt.trim() || !selectedBusiness || isGenerating) return;
    const instruction = prompt.trim();
    setIsGenerating(true);
    setStudioError("");
    setLatestAction(null);
    setLatestTrace({
      instruction,
      status: "submitting",
      tool_label: "Routing...",
      reason: "AI Studio is sending the prompt to the backend orchestrator.",
      started_at: new Date().toISOString(),
      steps: [
        {
          label: "Prompt queued",
          status: "active",
          detail: instruction,
          timestamp: new Date().toISOString(),
        },
      ],
    });
    setGenerationStep("Planning");

    try {
      const token = getToken();
      setMessages((current) => [
        ...current,
        {
          id: `pending-${Date.now()}`,
          role: "user",
          content: instruction,
          status: "pending",
          created_at: new Date().toISOString(),
        },
      ]);
      setGenerationStep("Applying");
      const selectedProjectId = selectedBusinessRecord?.project_id || (active.business_id === selectedBusiness ? active.project_id : null);
      const selectedWorkspaceId = selectedBusinessRecord?.workspace_id || (active.business_id === selectedBusiness ? active.workspace_id : null);
      if (!selectedProjectId) {
        throw new Error("AI Studio cannot find a real project for this business. Refresh workspace context or regenerate the project before sending prompts.");
      }
      const projectId = selectedProjectId;
      const workspaceId = selectedWorkspaceId || null;
      const res = await fetch(`${API_URL}/studio/projects/${projectId}/execute-prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          workspace_id: workspaceId,
          business_id: selectedBusiness,
          project_id: selectedProjectId || null,
          prompt: instruction,
          mode: "apply",
          brand_context: {
            tone_of_voice: brandContext.tone,
            target_audience: brandContext.audience,
            key_differentiators: brandContext.differentiators
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          },
        }),
      });

      setGenerationStep("Persisting");
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "AI Studio request failed");
      }

      if (data.status === "failed") {
        throw new Error(data.reason || data.action?.error || data.assistant_message?.content || "AI Studio could not complete the action.");
      }
      const action = data.action || {
        action_type: "app_builder_project_update",
        summary: data.summary,
        changed_files: data.changed_files || [],
        updated_files: data.changed_files || [],
        provider_used: data.provider,
        version_id: data.version_id,
        preview_url: data.preview_url,
        orchestration: data.timeline,
      };
      setLatestAction(action || null);
      setLatestTrace(asOrchestrationTrace(action?.orchestration) || asOrchestrationTrace(data.timeline) || null);
      await loadTimeline(selectedBusiness);
      if (action?.diff) {
        setLatestDiff(action.diff);
      }
      if (action?.summary) {
        setAppliedNotice(action.summary);
      }
      const actionType = String(action?.action_type || "");
      setGenerationStep(actionType === "code_edit_applied" ? "Persisting" : "Rendering");
      const nextKey = Date.now();
      if (actionType === "business_profile_update" || actionType === "app_builder_project_update") {
        const snapshot = await loadPreviewSnapshot(selectedBusiness, nextKey).catch(() => null);
        if (action?.summary && snapshot) {
          const changedField = action?.diff?.field;
          const visibleValue =
            changedField === "headline"
              ? snapshot.headline
              : changedField === "subheading"
                ? snapshot.subheading
                : changedField === "cta_text"
                  ? snapshot.cta_text
                  : changedField === "page_content"
                    ? snapshot.page_content?.urgency_text || snapshot.page_content?.color_scheme
                    : snapshot.headline || snapshot.cta_text || "preview saved";
          setAppliedNotice(`${action.summary} Live preview now reads: ${visibleValue}`);
        }
        setPreviewKey(nextKey);
        setPreviewUrl(`${window.location.origin}/landing/${selectedBusiness}?preview=1&refresh=${data.preview_version || nextKey}`);
        if (actionType === "app_builder_project_update") {
          const changed = action?.changed_files || action?.updated_files || [];
          setAppliedNotice(`${action.summary} Changed files: ${changed.length ? changed.join(", ") : "preview data"}.`);
        }
      } else if (actionType === "code_edit_applied") {
        setAppliedNotice(`${action.summary} Open AI Code Editor to review ${action.file_path || "the changed file"}.`);
      } else if (actionType === "research_report_created") {
        setAppliedNotice(`${action.summary} Open Agent Live to review the saved report.`);
      } else if (actionType === "marketing_campaign_created") {
        setAppliedNotice(`${action.summary} Open Marketing Engine to edit or publish it.`);
      } else if (actionType === "product_created") {
        setAppliedNotice(`${action.summary} Open Products to manage the offer.`);
      }
      setGenerationStep("Complete");
    } catch (error) {
      setStudioError(studioSafeError(error));
      await loadTimeline(selectedBusiness).catch(() => {});
    } finally {
      setIsGenerating(false);
      setPrompt("");
      window.setTimeout(() => setGenerationStep(null), 500);
    }
  }

  async function handleUndo() {
    if (versions.length < 2 || isGenerating) return;
    const targetVersion = versions[1];
    if (!targetVersion.versionId) return;
    setIsGenerating(true);
    setGenerationStep("Applying");
    setStudioError("");
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/code-editor/revert`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ business_id: selectedBusiness, version_id: targetVersion.versionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Undo failed");
      setGenerationStep("Rendering");
      await loadTimeline(selectedBusiness);
      setPreviewKey((k) => k + 1);
    } catch (error) {
      setStudioError(error instanceof Error ? error.message : "Undo failed");
    } finally {
      setIsGenerating(false);
      window.setTimeout(() => setGenerationStep(null), 500);
    }
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
            disabled={versions.length < 2 || isGenerating}
            title="Restore previous AI Studio snapshot"
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
              background: versions.length >= 2 && !isGenerating ? "#1e293b" : "#0f172a",
              border: "1px solid #334155", borderRadius: 6, color: versions.length >= 2 && !isGenerating ? "#e2e8f0" : "#475569",
              cursor: versions.length >= 2 && !isGenerating ? "pointer" : "not-allowed", fontSize: 13,
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

              {studioError && (
                <div style={{ marginTop: 12, padding: "10px 12px", background: "#3b1118", border: "1px solid #7f1d1d", borderRadius: 8, color: "#fecaca", fontSize: 12, lineHeight: 1.5 }}>
                  {studioError}
                </div>
              )}

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
              {messages.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 12 }}>
                    Conversation History
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {messages.slice(-8).map((message) => (
                      <div key={message.id} style={{ display: "flex", gap: 8, alignSelf: message.role === "user" ? "flex-end" : "flex-start", maxWidth: "88%" }}>
                        {message.role === "assistant" && (
                          <div style={{ width: 24, height: 24, borderRadius: "50%", background: "#1e293b", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                            <Bot size={14} color="#818cf8" />
                          </div>
                        )}
                        <div
                          style={{
                            background: message.role === "user" ? "#4f46e5" : "#1e293b",
                            color: message.role === "user" ? "#fff" : "#e2e8f0",
                            padding: "8px 12px",
                            borderRadius: message.role === "user" ? "12px 12px 0 12px" : "12px 12px 12px 0",
                            fontSize: 13,
                            lineHeight: 1.4,
                            border: message.role === "assistant" ? "1px solid #334155" : "none",
                          }}
                        >
                          {message.content}
                          {message.metadata?.updated_files && Array.isArray(message.metadata.updated_files) && message.metadata.updated_files.length > 0 && (
                            <div style={{ marginTop: 6, color: "#a5b4fc", fontSize: 11 }}>
                              Updated: {message.metadata.updated_files.join(", ")}
                            </div>
                          )}
                          {typeof message.metadata?.next_url === "string" && (
                            <Link
                              href={message.metadata.next_url}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 6,
                                marginTop: 8,
                                color: "#c7d2fe",
                                fontSize: 11,
                                fontWeight: 700,
                                textDecoration: "none",
                              }}
                            >
                              Open generated asset
                              <ChevronRight size={12} />
                            </Link>
                          )}
                          {message.status === "pending" && (
                            <div style={{ marginTop: 4, color: "#c7d2fe", fontSize: 11 }}>
                              Waiting for orchestration...
                            </div>
                          )}
                          {message.status === "failed" && (
                            <div style={{ marginTop: 4, color: "#fecaca", fontSize: 11 }}>
                              Failed
                            </div>
                          )}
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
                onClick={() => {
                  const nextKey = Date.now();
                  setPreviewKey(nextKey);
                  setPreviewUrl(`${window.location.origin}/landing/${selectedBusiness}?preview=1&refresh=${nextKey}`);
                  if (selectedBusiness) loadPreviewSnapshot(selectedBusiness, nextKey).catch(() => {});
                }}
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
                    {versions.length} persisted changes
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

              {latestTrace && (
                <div style={{ padding: 12, background: "#0b1220", borderRadius: 12, border: latestTrace.status === "failed" ? "1px solid #7f1d1d" : "1px solid #1d4ed8" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
                    <div style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                      Backend Orchestration Trace
                    </div>
                    <span style={{ fontSize: 10, color: latestTrace.status === "failed" ? "#fecaca" : "#bfdbfe", border: "1px solid #334155", borderRadius: 999, padding: "3px 7px", textTransform: "uppercase", fontWeight: 800 }}>
                      {latestTrace.status || "running"}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "#e2e8f0", lineHeight: 1.55, marginBottom: 8, wordBreak: "break-word" }}>
                    <span style={{ color: "#64748b" }}>Prompt:</span> {latestTrace.instruction || "Waiting for backend prompt receipt..."}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 6, marginBottom: 8 }}>
                    <div style={{ fontSize: 12, color: "#cbd5e1" }}>
                      Tool: <span style={{ color: "#f8fafc", fontWeight: 800 }}>{latestTrace.tool_label || latestTrace.selected_tool || "Routing..."}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "#cbd5e1" }}>
                      Intent: <span style={{ color: "#a5b4fc", fontWeight: 700 }}>{latestTrace.intent?.replaceAll("_", " ") || "detecting"}</span>
                      {latestTrace.duration_ms !== undefined && (
                        <span style={{ color: "#64748b" }}> · {formatDuration(latestTrace.duration_ms)}</span>
                      )}
                    </div>
                    {latestTrace.provider_used && (
                      <div style={{ fontSize: 12, color: "#cbd5e1" }}>
                        Provider: <span style={{ color: "#f8fafc", fontWeight: 700 }}>{latestTrace.provider_used}</span>
                      </div>
                    )}
                  </div>
                  {latestTrace.reason && (
                    <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6, margin: "0 0 10px" }}>
                      {latestTrace.reason}
                    </p>
                  )}
                  {latestTrace.error && (
                    <div style={{ fontSize: 12, color: "#fecaca", background: "#3b1118", border: "1px solid #7f1d1d", borderRadius: 8, padding: "8px 9px", marginBottom: 10 }}>
                      {latestTrace.error}
                    </div>
                  )}
                  {latestTrace.steps && latestTrace.steps.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                      {latestTrace.steps.slice(0, 6).map((step, index) => (
                        <div key={`${step.label}-${index}`} style={{ display: "grid", gridTemplateColumns: "14px 1fr", gap: 8 }}>
                          <span style={{ width: 9, height: 9, borderRadius: "50%", marginTop: 4, background: step.status === "failed" ? "#ef4444" : step.status === "active" ? "#fbbf24" : "#22c55e", boxShadow: "0 0 0 3px rgba(148,163,184,0.08)" }} />
                          <div>
                            <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 700 }}>{step.label || "Step"}</div>
                            {step.detail && (
                              <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.45, marginTop: 2, wordBreak: "break-word" }}>
                                {step.detail}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {latestTrace.updated_files && latestTrace.updated_files.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 10 }}>
                      {latestTrace.updated_files.slice(0, 4).map((file) => (
                        <span key={file} style={{ fontSize: 11, color: "#dbeafe", border: "1px solid #1d4ed8", borderRadius: 8, padding: "5px 7px", background: "rgba(29,78,216,0.14)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {file}
                        </span>
                      ))}
                    </div>
                  )}
                  {latestTrace.next_url && (
                    <Link
                      href={latestTrace.next_url}
                      style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, color: "#93c5fd", fontSize: 12, fontWeight: 700, textDecoration: "none" }}
                    >
                      Open routed module
                      <ChevronRight size={13} />
                    </Link>
                  )}
                </div>
              )}

              {latestAction && (
                <div style={{ padding: 12, background: "#101826", borderRadius: 12, border: "1px solid #2b3b52" }}>
                  <div style={{ fontSize: 11, color: "#67e8f9", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>
                    Execution Result
                  </div>
                  <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.6, marginBottom: 6 }}>
                    Type: <span style={{ color: "#f8fafc", fontWeight: 700 }}>{latestAction.action_type?.replaceAll("_", " ") || "completed"}</span>
                  </div>
                  {latestAction.provider_used && (
                    <div style={{ fontSize: 12, color: "#a5b4fc", lineHeight: 1.6, marginBottom: 6 }}>
                      Provider: {latestAction.provider_used}
                    </div>
                  )}
                  {latestAction.file_path && (
                    <div style={{ fontSize: 12, color: "#a5b4fc", lineHeight: 1.6, marginBottom: 6 }}>
                      File: {latestAction.file_path}
                    </div>
                  )}
                  {latestAction.campaign_name && (
                    <div style={{ fontSize: 12, color: "#a5b4fc", lineHeight: 1.6, marginBottom: 6 }}>
                      Campaign: {latestAction.campaign_name}
                    </div>
                  )}
                  {((latestAction.changed_files && latestAction.changed_files.length > 0) || (latestAction.updated_files && latestAction.updated_files.length > 0)) && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                      {(latestAction.changed_files || latestAction.updated_files || []).slice(0, 4).map((file) => (
                        <span key={file} style={{ fontSize: 11, color: "#cbd5e1", border: "1px solid #334155", borderRadius: 8, padding: "5px 7px", background: "#0f172a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {file}
                        </span>
                      ))}
                    </div>
                  )}
                  {latestAction.summary && (
                    <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.65, margin: "10px 0 0" }}>
                      {latestAction.summary}
                    </p>
                  )}
                  {latestAction.next_url && (
                    <Link
                      href={latestAction.next_url}
                      style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, color: "#93c5fd", fontSize: 12, fontWeight: 700, textDecoration: "none" }}
                    >
                      Open result
                      <ChevronRight size={13} />
                    </Link>
                  )}
                </div>
              )}

              {previewSnapshot && (
                <div style={{ padding: 12, background: "#111827", borderRadius: 12, border: "1px solid #243041" }}>
                  <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>
                    Live Preview Data
                  </div>
                  <div style={{ fontSize: 12, color: "#e2e8f0", lineHeight: 1.6, marginBottom: 6 }}>
                    Headline: {previewSnapshot.headline || "Not set"}
                  </div>
                  <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.6, marginBottom: 6 }}>
                    CTA: {previewSnapshot.cta_text || "Not set"}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>
                    Theme: {previewSnapshot.page_content?.color_scheme || "default"}
                  </div>
                  {previewSnapshot.page_content?.urgency_text && (
                    <div style={{ marginTop: 6, fontSize: 12, color: "#fde68a", lineHeight: 1.6 }}>
                      Urgency: {previewSnapshot.page_content.urgency_text}
                    </div>
                  )}
                </div>
              )}

              <div style={{ padding: 14, background: "#111827", borderRadius: 12, border: "1px solid #1f2937" }}>
                <p style={{ fontSize: 11, color: "#64748b", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", margin: "0 0 8px" }}>
                  Execution history
                </p>
                {timelineActions.length === 0 ? (
                  <p style={{ color: "#475569", fontSize: 13, margin: 0 }}>No real backend executions yet. Send a prompt to start the orchestration timeline.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {timelineActions.slice(0, 5).map((item) => (
                      <div key={item.id} style={{ borderRadius: 10, border: "1px solid #243041", padding: "10px 12px", background: "#0f172a" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
                          <span style={{ fontSize: 10, color: item.status === "failed" ? "#fecaca" : "#a5b4fc", fontWeight: 800, textTransform: "uppercase" }}>
                            {item.trace?.tool_label || item.action_type?.replaceAll("_", " ") || "AI Studio"}
                          </span>
                          <span style={{ fontSize: 10, color: "#64748b", whiteSpace: "nowrap" }}>{item.timestamp}</span>
                        </div>
                        <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 700, marginBottom: 5, lineHeight: 1.45, wordBreak: "break-word" }}>
                          {item.prompt}
                        </div>
                        <div style={{ fontSize: 11, color: item.status === "failed" ? "#fca5a5" : "#94a3b8", lineHeight: 1.45, wordBreak: "break-word" }}>
                          {item.response}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
      {appliedNotice && (
        <div style={{ position: "fixed", right: 22, bottom: 22, zIndex: 80, maxWidth: 360, display: "flex", alignItems: "center", gap: 10, padding: "11px 13px", borderRadius: 14, background: "rgba(15,23,42,0.94)", border: "1px solid rgba(34,197,94,0.34)", boxShadow: "0 18px 52px rgba(15,23,42,0.4), 0 0 34px rgba(34,197,94,0.16)", color: "#e2e8f0", fontSize: 12, lineHeight: 1.35, animation: "slideInRight .18s ease" }}>
          <CheckCircle size={16} color="#86efac" style={{ flexShrink: 0 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ color: "#86efac", fontWeight: 900, marginBottom: 1 }}>Applied</div>
            <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{appliedNotice}</div>
          </div>
        </div>
      )}
    </>
  );
}
