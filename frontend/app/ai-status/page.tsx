"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle,
  XCircle,
  RefreshCw,
  Cpu,
  Cloud,
  Zap,
  AlertTriangle,
  Activity,
} from "lucide-react";

type AIHealth = {
  groq: boolean;
  huggingface: boolean;
  ollama: boolean;
  any_available: boolean;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const PROVIDERS = [
  {
    key: "groq" as const,
    label: "Groq",
    desc: "Primary hosted provider for AI Studio, marketing, code edits, and fast JSON tasks.",
    icon: Zap,
    priority: 1,
    setup: "Get a free key at console.groq.com.",
    url: "https://console.groq.com",
    envVar: "GROQ_API_KEY",
    gradient: "linear-gradient(135deg,#6366f1,#8b5cf6)",
    glow: "rgba(99,102,241,0.3)",
  },
  {
    key: "ollama" as const,
    label: "Ollama (Local)",
    desc: "Local fallback for offline or degraded-mode execution.",
    icon: Cpu,
    priority: 2,
    setup: "Install Ollama, then run: ollama pull llama3",
    url: "https://ollama.com",
    envVar: null,
    gradient: "linear-gradient(135deg,#10b981,#059669)",
    glow: "rgba(16,185,129,0.3)",
  },
  {
    key: "huggingface" as const,
    label: "Hugging Face",
    desc: "Hosted fallback inference when the main providers fail.",
    icon: Cloud,
    priority: 3,
    setup: "Get a token at huggingface.co/settings/tokens.",
    url: "https://huggingface.co/settings/tokens",
    envVar: "HF_API_KEY",
    gradient: "linear-gradient(135deg,#f59e0b,#ef4444)",
    glow: "rgba(245,158,11,0.3)",
  },
];

export default function AIStatusPage() {
  const [health, setHealth] = useState<AIHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  async function fetchHealth() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/ai/health`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHealth(await res.json());
      setLastChecked(new Date());
    } catch (err: any) {
      setError(err.message || "Could not reach the backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchHealth();
  }, []);

  const available = health
    ? [health.groq, health.huggingface, health.ollama].filter(Boolean).length
    : 0;

  return (
    <div className="anim-fade-in" style={{ maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Activity size={24} style={{ color: "#6366f1" }} /> AI Provider Status
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>
          Real provider routing only. Featherless is disabled; active routing uses Groq, Ollama, and Hugging Face.
        </p>
      </div>

      <div
        style={{
          borderRadius: 16,
          border: `1.5px solid ${loading ? "#e2e8f0" : error ? "#fecaca" : health?.any_available ? "#bbf7d0" : "#fde68a"}`,
          background: loading ? "#f8fafc" : error ? "#fef2f2" : health?.any_available ? "#f0fdf4" : "#fffbeb",
          padding: "18px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {loading ? (
            <RefreshCw size={18} className="animate-spin" style={{ color: "#94a3b8" }} />
          ) : error ? (
            <XCircle size={18} style={{ color: "#dc2626" }} />
          ) : health?.any_available ? (
            <CheckCircle size={18} style={{ color: "#16a34a" }} />
          ) : (
            <AlertTriangle size={18} style={{ color: "#d97706" }} />
          )}
          <div>
            <p style={{ fontWeight: 700, fontSize: 14, margin: 0, color: loading ? "#64748b" : error ? "#dc2626" : health?.any_available ? "#15803d" : "#92400e" }}>
              {loading
                ? "Checking providers..."
                : error
                  ? `Backend unreachable: ${error}`
                  : health?.any_available
                    ? `AI operational — ${available} provider${available > 1 ? "s" : ""} available`
                    : "No AI providers configured"}
            </p>
            {!loading && !error && !health?.any_available && (
              <p style={{ fontSize: 12, color: "#b45309", margin: "2px 0 0" }}>
                Configure GROQ_API_KEY or HF_API_KEY in backend/.env, or keep Ollama running locally.
              </p>
            )}
          </div>
        </div>
        {!loading && health && (
          <div style={{ display: "flex", gap: 6 }}>
            {[health.groq, health.huggingface, health.ollama].map((ok, i) => (
              <div key={i} style={{ width: 10, height: 10, borderRadius: "50%", background: ok ? "#22c55e" : "#e2e8f0" }} />
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {PROVIDERS.map(({ key, label, desc, icon: Icon, priority, setup, url, envVar, gradient, glow }) => {
          const ok = health?.[key] ?? false;
          return (
            <div
              key={key}
              className="card-lift"
              style={{ background: "#fff", borderRadius: 18, border: `1.5px solid ${ok ? "#bbf7d0" : "#e2e8f0"}`, padding: "20px 22px" }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                  <div style={{ width: 48, height: 48, borderRadius: 14, background: gradient, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 6px 20px ${glow}`, flexShrink: 0 }}>
                    <Icon size={22} color="#fff" />
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <h2 style={{ fontWeight: 800, fontSize: 15, color: "#0f172a", margin: 0 }}>{label}</h2>
                      <span style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 99 }}>
                        Priority {priority}
                      </span>
                    </div>
                    <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>{desc}</p>
                  </div>
                </div>
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    flexShrink: 0,
                    borderRadius: 99,
                    padding: "5px 12px",
                    fontSize: 12,
                    fontWeight: 700,
                    background: loading ? "#f1f5f9" : ok ? "#dcfce7" : "#f1f5f9",
                    color: loading ? "#94a3b8" : ok ? "#16a34a" : "#94a3b8",
                  }}
                >
                  {loading ? <RefreshCw size={11} className="animate-spin" /> : ok ? <CheckCircle size={11} /> : <XCircle size={11} />}
                  {loading ? "Checking" : ok ? "Available" : "Not configured"}
                </span>
              </div>

              {!ok && !loading && (
                <div style={{ marginTop: 14, background: "#f8fafc", borderRadius: 12, border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                  {envVar && (
                    <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 6px" }}>
                      Add to <code style={{ background: "#e2e8f0", padding: "1px 6px", borderRadius: 4, fontSize: 12 }}>backend/.env</code>:{" "}
                      <code style={{ background: "#e2e8f0", padding: "1px 6px", borderRadius: 4, fontSize: 12 }}>{envVar}=your_key_here</code>
                    </p>
                  )}
                  <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 8px" }}>{setup}</p>
                  <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, fontWeight: 600, color: "#6366f1", textDecoration: "none" }}>
                    Learn more →
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <button
          onClick={fetchHealth}
          disabled={loading}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "#fff",
            border: "1.5px solid #e2e8f0",
            borderRadius: 12,
            padding: "10px 18px",
            fontSize: 13,
            fontWeight: 700,
            color: "#374151",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1,
            fontFamily: "inherit",
          }}
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh Status
        </button>
        {lastChecked && <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Last checked: {lastChecked.toLocaleTimeString()}</p>}
      </div>
    </div>
  );
}
