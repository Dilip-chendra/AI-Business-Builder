"use client";
import { useEffect, useState } from "react";
import { CheckCircle, Circle, X, Sparkles, ChevronDown, ChevronUp } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Step = { id: string; label: string; completed: boolean };
type OnboardingStatus = {
  steps: Step[];
  completed_count: number;
  total_count: number;
  all_complete: boolean;
  onboarding_complete: boolean;
};

export function OnboardingChecklist() {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) return;
    fetch(`${API_URL}/onboarding/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setStatus(d); })
      .catch(() => {});
  }, []);

  async function completeStep(stepId: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/onboarding/complete/${stepId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) setStatus(await r.json());
    } catch {}
  }

  // Don't show if dismissed, all complete, or no data
  if (dismissed || !status || status.onboarding_complete) return null;

  const progress = Math.round((status.completed_count / status.total_count) * 100);

  return (
    <div style={{
      background: "#fff",
      borderRadius: 16,
      border: "1.5px solid #c4b5fd",
      boxShadow: "0 4px 24px rgba(99,102,241,0.12)",
      overflow: "hidden",
      marginBottom: 8,
    }}>
      {/* Header */}
      <div style={{ padding: "14px 16px", background: "linear-gradient(135deg,#0f172a,#1e1b4b)", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Sparkles size={14} color="#fff" />
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: "#fff", margin: 0 }}>Getting Started</p>
          <p style={{ fontSize: 11, color: "rgba(255,255,255,0.5)", margin: 0 }}>{status.completed_count}/{status.total_count} steps complete</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setCollapsed(c => !c)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.5)", padding: 4, display: "flex", alignItems: "center" }} aria-label={collapsed ? "Expand checklist" : "Collapse checklist"}>
            {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
          <button onClick={() => setDismissed(true)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", padding: 4, display: "flex", alignItems: "center" }} aria-label="Dismiss onboarding checklist">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: "#e2e8f0" }}>
        <div style={{ width: `${progress}%`, height: "100%", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", transition: "width 0.4s ease" }} />
      </div>

      {/* Steps */}
      {!collapsed && (
        <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          {status.steps.map(step => (
            <div key={step.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button
                onClick={() => !step.completed && completeStep(step.id)}
                style={{ background: "none", border: "none", cursor: step.completed ? "default" : "pointer", padding: 0, display: "flex", alignItems: "center", flexShrink: 0 }}
                aria-label={step.completed ? `${step.label} completed` : `Mark ${step.label} as complete`}
              >
                {step.completed
                  ? <CheckCircle size={18} color="#10b981" />
                  : <Circle size={18} color="#cbd5e1" />}
              </button>
              <span style={{ fontSize: 13, color: step.completed ? "#94a3b8" : "#374151", fontWeight: step.completed ? 400 : 500, textDecoration: step.completed ? "line-through" : "none" }}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
