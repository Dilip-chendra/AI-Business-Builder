"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { Activity, Zap, Cloud, Cpu, AlertTriangle, CheckCircle, XCircle, RefreshCw, TrendingUp, Clock, BarChart3, Shield, Radio, GitBranch, RotateCcw, BrainCircuit } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type ProviderData = {
  name: string; total_requests: number; total_successes: number;
  total_failures: number; total_timeouts: number; total_rate_limits: number;
  success_rate_pct: number; avg_latency_ms: number;
  circuit_state: "closed"|"open"|"half-open"; score: number;
  is_available: boolean; health: "green"|"yellow"|"red";
};
type SystemData = { total_requests: number; total_fallbacks: number; fallback_rate_pct: number; uptime_seconds: number };
type FailureRecord = { trace_id: string; provider: string; error_type: string; error_message: string; latency_ms: number; timestamp: number; prompt_preview: string };
type TelemetryData = { providers: Record<string,ProviderData>; system: SystemData; recent_failures: FailureRecord[] };
type LatencyData = { providers: Record<string, { p50: number; p95: number; p99: number; avg: number }> };
type FallbackEvent = { from_provider: string; to_provider: string; reason: string; error_message: string; timestamp: number; trace_id: string };
type FallbackData = { total_fallbacks: number; fallback_rate_pct: number; events: FallbackEvent[] };
type RoutingProvider = { provider: string; priority: number; configured: boolean; circuit_state: string; score: number; fallback_condition: string };
type RoutingData = { routing_strategy: string; description: string; providers: RoutingProvider[]; circuit_breaker_threshold: number; circuit_breaker_cooldown_seconds: number };
type LiveEvent = { type: string; total_requests: number; total_fallbacks: number; providers: Record<string, { health: string; score: number; circuit_state: string; avg_latency_ms: number }>; timestamp: number };

const PROVIDER_ICONS: Record<string,any> = { featherless: BrainCircuit, groq: Zap, huggingface: Cloud, ollama: Cpu };
const PROVIDER_COLORS: Record<string,string> = { featherless: "#0f172a", groq: "#6366f1", huggingface: "#f59e0b", ollama: "#10b981" };

function HealthDot({ health }: { health: string }) {
  const colors: Record<string,string> = { green: "#10b981", yellow: "#f59e0b", red: "#ef4444" };
  const c = colors[health] || "#94a3b8";
  return <div style={{ width: 10, height: 10, borderRadius: "50%", background: c, boxShadow: `0 0 6px ${c}`, flexShrink: 0 }} />;
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.08)", borderRadius: 99, overflow: "hidden" }}>
        <div style={{ width: `${score}%`, height: "100%", background: color, borderRadius: 99, transition: "width 0.5s ease" }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32 }}>{score}</span>
    </div>
  );
}

function CircuitBadge({ state }: { state: string }) {
  const cfg: Record<string,{bg:string;color:string;label:string}> = {
    closed:    { bg: "rgba(16,185,129,0.15)", color: "#34d399", label: "Closed" },
    open:      { bg: "rgba(239,68,68,0.15)",  color: "#f87171", label: "Open" },
    "half-open": { bg: "rgba(245,158,11,0.15)", color: "#fbbf24", label: "Half-Open" },
  };
  const s = cfg[state] || cfg.closed;
  return <span style={{ background: s.bg, color: s.color, fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99 }}>{s.label}</span>;
}

export default function OpsPage() {
  const [data, setData] = useState<TelemetryData|null>(null);
  const [latencyData, setLatencyData] = useState<LatencyData|null>(null);
  const [fallbackData, setFallbackData] = useState<FallbackData|null>(null);
  const [routingData, setRoutingData] = useState<RoutingData|null>(null);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [resetting, setResetting] = useState<string|null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date|null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string|null>(null);
  const esRef = useRef<EventSource|null>(null);

  const fetch_data = useCallback(async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) { setError("Not authenticated"); setLoading(false); return; }
    const h = { Authorization: `Bearer ${token}` };
    try {
      const [r1, r2, r3, r4] = await Promise.all([
        fetch(`${API_URL}/ai/telemetry/health`, { headers: h }),
        fetch(`${API_URL}/ai/telemetry/latency`, { headers: h }),
        fetch(`${API_URL}/ai/telemetry/fallbacks`, { headers: h }),
        fetch(`${API_URL}/ai/telemetry/routing`, { headers: h }),
      ]);
      if (!r1.ok) throw new Error(`HTTP ${r1.status}`);
      const [d1, d2, d3, d4] = await Promise.all([r1.json(), r2.ok ? r2.json() : null, r3.ok ? r3.json() : null, r4.ok ? r4.json() : null]);
      setData(d1); setLastUpdated(new Date()); setError(null);
      if (d2) setLatencyData(d2);
      if (d3) setFallbackData(d3);
      if (d4) setRoutingData(d4);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  // Start SSE live events stream
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) return;
    const es = new EventSource(`${API_URL}/ai/telemetry/stream?token=${token}`);
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const evt: LiveEvent = JSON.parse(e.data);
        setLiveEvents(prev => [evt, ...prev].slice(0, 20));
      } catch {}
    };
    es.onerror = () => { es.close(); };
    return () => { es.close(); };
  }, []);

  async function resetCircuit(provider: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) return;
    setResetting(provider);
    try {
      await fetch(`${API_URL}/ai/telemetry/reset/${provider}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetch_data();
    } catch {}
    finally { setResetting(null); }
  }

  useEffect(() => { fetch_data(); }, [fetch_data]);
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetch_data, 7000);
    return () => clearInterval(id);
  }, [autoRefresh, fetch_data]);

  const providers = data ? Object.values(data.providers) : [];
  const sys = data?.system;
  const failures = data?.recent_failures || [];

  const overallHealth = providers.length === 0 ? "unknown"
    : providers.every(p => p.health === "green") ? "green"
    : providers.some(p => p.health === "red") ? "red" : "yellow";

  const healthColors: Record<string,string> = { green: "#10b981", yellow: "#f59e0b", red: "#ef4444", unknown: "#94a3b8" };

  return (
    <div className="anim-fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <Activity size={24} style={{ color: "#6366f1" }} /> AI Operations
          </h1>
          <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>
            Real-time provider health, circuit breaker state, and failure log.
            {lastUpdated && <span style={{ marginLeft: 8, color: "#94a3b8" }}>Updated {lastUpdated.toLocaleTimeString()}</span>}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#64748b", cursor: "pointer" }}>
            <div onClick={() => setAutoRefresh(!autoRefresh)}
              style={{ width: 36, height: 20, borderRadius: 99, background: autoRefresh ? "#6366f1" : "#e2e8f0", position: "relative", cursor: "pointer", transition: "background 0.2s" }}>
              <div style={{ position: "absolute", top: 2, left: autoRefresh ? 18 : 2, width: 16, height: 16, borderRadius: "50%", background: "#fff", transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)" }} />
            </div>
            Auto-refresh
          </label>
          <button onClick={fetch_data} aria-label="Refresh telemetry data" style={{ display: "flex", alignItems: "center", gap: 6, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "8px 14px", fontSize: 13, fontWeight: 600, color: "#374151", cursor: "pointer", fontFamily: "inherit" }}>
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{ display: "flex", gap: 8, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>
          <AlertTriangle size={15} style={{ flexShrink: 0 }} /> {error}
        </div>
      )}

      {/* Overall status banner */}
      <div style={{ borderRadius: 18, background: `linear-gradient(135deg, #0f172a, #1e1b4b)`, padding: "20px 28px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: healthColors[overallHealth], boxShadow: `0 0 10px ${healthColors[overallHealth]}` }} />
          <div>
            <p style={{ fontSize: 16, fontWeight: 800, color: "#fff", margin: 0 }}>
              System {overallHealth === "green" ? "Healthy" : overallHealth === "yellow" ? "Degraded" : overallHealth === "red" ? "Failing" : "Unknown"}
            </p>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", margin: 0 }}>
              {providers.filter(p => p.is_available).length}/{providers.length} providers available
            </p>
          </div>
        </div>
        {sys && (
          <div style={{ display: "flex", gap: 20 }}>
            {[
              { label: "Total Requests", value: sys.total_requests.toLocaleString() },
              { label: "Fallbacks", value: sys.total_fallbacks.toLocaleString() },
              { label: "Fallback Rate", value: `${sys.fallback_rate_pct}%` },
              { label: "Uptime", value: `${Math.floor(sys.uptime_seconds / 60)}m` },
            ].map(({ label, value }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <p style={{ fontSize: 20, fontWeight: 900, color: "#fff", margin: 0 }}>{value}</p>
                <p style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", margin: 0 }}>{label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Provider cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
        {loading && !data ? (
          [1,2,3].map(i => <div key={i} style={{ height: 220, borderRadius: 18, background: "#f1f5f9", animation: "shimmer 1.5s infinite" }} />)
        ) : (
          providers.map(p => {
            const Icon = PROVIDER_ICONS[p.name] || Activity;
            const color = PROVIDER_COLORS[p.name] || "#6366f1";
            return (
              <div key={p.name} style={{ background: "#fff", borderRadius: 18, border: `1.5px solid ${p.health === "red" ? "#fecaca" : p.health === "yellow" ? "#fde68a" : "#e2e8f0"}`, padding: "20px 22px", boxShadow: "0 2px 12px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 38, height: 38, borderRadius: 10, background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Icon size={18} style={{ color }} />
                    </div>
                    <div>
                      <p style={{ fontWeight: 800, fontSize: 15, color: "#0f172a", margin: 0, textTransform: "capitalize" }}>{p.name}</p>
                      <CircuitBadge state={p.circuit_state} />
                    </div>
                  </div>
                  <HealthDot health={p.health} />
                </div>

                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>Provider Score</span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>0 — 100</span>
                  </div>
                  <ScoreBar score={p.score} />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {[
                    { label: "Success Rate", value: `${p.success_rate_pct}%`, color: p.success_rate_pct >= 90 ? "#10b981" : p.success_rate_pct >= 70 ? "#f59e0b" : "#ef4444" },
                    { label: "Avg Latency", value: p.avg_latency_ms > 0 ? `${Math.round(p.avg_latency_ms)}ms` : "—", color: p.avg_latency_ms < 500 ? "#10b981" : p.avg_latency_ms < 1500 ? "#f59e0b" : "#ef4444" },
                    { label: "Failures", value: p.total_failures.toString(), color: p.total_failures === 0 ? "#10b981" : "#ef4444" },
                    { label: "Timeouts", value: p.total_timeouts.toString(), color: p.total_timeouts === 0 ? "#10b981" : "#f59e0b" },
                    { label: "Rate Limits", value: p.total_rate_limits.toString(), color: p.total_rate_limits === 0 ? "#10b981" : "#f59e0b" },
                    { label: "Total Calls", value: p.total_requests.toString(), color: "#6366f1" },
                  ].map(({ label, value, color: vc }) => (
                    <div key={label} style={{ background: "#f8fafc", borderRadius: 8, padding: "8px 10px" }}>
                      <p style={{ fontSize: 10, color: "#94a3b8", margin: "0 0 2px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</p>
                      <p style={{ fontSize: 16, fontWeight: 800, color: vc, margin: 0 }}>{value}</p>
                    </div>
                  ))}
                </div>

                {/* Task 10.4: Reset Circuit button */}
                {p.circuit_state !== "closed" && (
                  <button
                    onClick={() => resetCircuit(p.name)}
                    disabled={resetting === p.name}
                    style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, width: "100%", padding: "8px", borderRadius: 8, border: "1px solid #fecaca", background: "#fef2f2", color: "#dc2626", fontSize: 12, fontWeight: 700, cursor: resetting === p.name ? "not-allowed" : "pointer", fontFamily: "inherit", opacity: resetting === p.name ? 0.6 : 1 }}
                  >
                    <RotateCcw size={12} />
                    {resetting === p.name ? "Resetting..." : "Reset Circuit"}
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Failure log */}
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle size={15} style={{ color: "#f59e0b" }} />
          <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
            Recent Failures <span style={{ color: "#94a3b8", fontWeight: 500 }}>({failures.length})</span>
          </h2>
        </div>
        {failures.length === 0 ? (
          <div style={{ padding: "32px", textAlign: "center" }}>
            <CheckCircle size={28} style={{ color: "#10b981", margin: "0 auto 8px" }} />
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>No failures recorded — all providers healthy</p>
          </div>
        ) : (
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            {failures.map((f, i) => (
              <div key={i} style={{ display: "flex", gap: 12, padding: "12px 20px", borderBottom: "1px solid #f8fafc", alignItems: "flex-start" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", flexShrink: 0, marginTop: 5 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: PROVIDER_COLORS[f.provider] || "#6366f1", textTransform: "capitalize" }}>{f.provider}</span>
                    <span style={{ fontSize: 10, background: "#fee2e2", color: "#dc2626", padding: "1px 6px", borderRadius: 99, fontWeight: 700 }}>{f.error_type}</span>
                    <span style={{ fontSize: 10, color: "#94a3b8" }}>{Math.round(f.latency_ms)}ms</span>
                    <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: "auto" }}>{new Date(f.timestamp * 1000).toLocaleTimeString()}</span>
                  </div>
                  <p style={{ fontSize: 12, color: "#374151", margin: "0 0 2px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.error_message}</p>
                  {f.prompt_preview && <p style={{ fontSize: 11, color: "#94a3b8", margin: 0, fontStyle: "italic", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>"{f.prompt_preview}"</p>}
                </div>
                <span style={{ fontSize: 10, color: "#94a3b8", flexShrink: 0 }}>#{f.trace_id}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Task 9.4: Latency percentile chart */}
      {latencyData && (
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <TrendingUp size={15} style={{ color: "#6366f1" }} />
            <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Latency Percentiles (p50 / p95 / p99)</h2>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {Object.entries(latencyData.providers).map(([name, lp]) => {
              const color = PROVIDER_COLORS[name] || "#6366f1";
              const maxMs = Math.max(lp.p99, 1);
              return (
                <div key={name}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color, textTransform: "capitalize", minWidth: 90 }}>{name}</span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>avg {lp.avg}ms</span>
                  </div>
                  {[{ label: "p50", val: lp.p50, c: "#10b981" }, { label: "p95", val: lp.p95, c: "#f59e0b" }, { label: "p99", val: lp.p99, c: "#ef4444" }].map(({ label, val, c }) => (
                    <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 700, color: c, minWidth: 28 }}>{label}</span>
                      <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 99, overflow: "hidden" }}>
                        <div style={{ width: `${Math.min(100, (val / maxMs) * 100)}%`, height: "100%", background: c, borderRadius: 99, transition: "width 0.5s ease" }} />
                      </div>
                      <span style={{ fontSize: 11, color: "#374151", minWidth: 50, textAlign: "right" }}>{val}ms</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Task 10.3: Fallback history log */}
      {fallbackData && (
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
          <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", gap: 8 }}>
            <GitBranch size={15} style={{ color: "#f59e0b" }} />
            <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
              Fallback History
              <span style={{ color: "#94a3b8", fontWeight: 500, marginLeft: 6 }}>({fallbackData.total_fallbacks} total, {fallbackData.fallback_rate_pct}% rate)</span>
            </h2>
          </div>
          {fallbackData.events.length === 0 ? (
            <div style={{ padding: "28px", textAlign: "center" }}>
              <CheckCircle size={24} style={{ color: "#10b981", margin: "0 auto 8px" }} />
              <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>No fallbacks recorded</p>
            </div>
          ) : (
            <div style={{ maxHeight: 300, overflowY: "auto" }}>
              {fallbackData.events.slice(0, 20).map((ev, i) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: "10px 20px", borderBottom: "1px solid #f8fafc", alignItems: "center" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: PROVIDER_COLORS[ev.from_provider] || "#6366f1", textTransform: "capitalize", minWidth: 80 }}>{ev.from_provider}</span>
                  <span style={{ fontSize: 10, color: "#94a3b8" }}>fell back to</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#10b981", textTransform: "capitalize" }}>{ev.to_provider}</span>
                  <span style={{ fontSize: 10, background: "#fef3c7", color: "#d97706", padding: "1px 6px", borderRadius: 99, fontWeight: 700 }}>{ev.reason}</span>
                  <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: "auto" }}>{new Date(ev.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Failure log */}
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle size={15} style={{ color: "#f59e0b" }} />
          <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>
            Recent Failures <span style={{ color: "#94a3b8", fontWeight: 500 }}>({failures.length})</span>
          </h2>
        </div>
        {failures.length === 0 ? (
          <div style={{ padding: "32px", textAlign: "center" }}>
            <CheckCircle size={28} style={{ color: "#10b981", margin: "0 auto 8px" }} />
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>No failures recorded — all providers healthy</p>
          </div>
        ) : (
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            {failures.map((f, i) => (
              <div key={i} style={{ display: "flex", gap: 12, padding: "12px 20px", borderBottom: "1px solid #f8fafc", alignItems: "flex-start" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", flexShrink: 0, marginTop: 5 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: PROVIDER_COLORS[f.provider] || "#6366f1", textTransform: "capitalize" }}>{f.provider}</span>
                    <span style={{ fontSize: 10, background: "#fee2e2", color: "#dc2626", padding: "1px 6px", borderRadius: 99, fontWeight: 700 }}>{f.error_type}</span>
                    <span style={{ fontSize: 10, color: "#94a3b8" }}>{Math.round(f.latency_ms)}ms</span>
                    <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: "auto" }}>{new Date(f.timestamp * 1000).toLocaleTimeString()}</span>
                  </div>
                  <p style={{ fontSize: 12, color: "#374151", margin: "0 0 2px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.error_message}</p>
                  {f.prompt_preview && <p style={{ fontSize: 11, color: "#94a3b8", margin: 0, fontStyle: "italic", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>"{f.prompt_preview}"</p>}
                </div>
                <span style={{ fontSize: 10, color: "#94a3b8", flexShrink: 0 }}>#{f.trace_id}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Task 11.3: Live SSE events panel */}
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", gap: 8 }}>
          <Radio size={15} style={{ color: "#10b981" }} />
          <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Live Events</h2>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 6px #10b981", marginLeft: 4 }} />
        </div>
        {liveEvents.length === 0 ? (
          <div style={{ padding: "28px", textAlign: "center" }}>
            <Radio size={24} style={{ color: "#cbd5e1", margin: "0 auto 8px" }} />
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>Waiting for live events...</p>
          </div>
        ) : (
          <div style={{ maxHeight: 280, overflowY: "auto", fontFamily: "monospace" }}>
            {liveEvents.map((ev, i) => (
              <div key={i} style={{ display: "flex", gap: 12, padding: "8px 20px", borderBottom: "1px solid #f8fafc", alignItems: "center", background: i === 0 ? "#f0fdf4" : "transparent" }}>
                <span style={{ fontSize: 10, color: "#10b981", fontWeight: 700, minWidth: 120 }}>{ev.type}</span>
                <span style={{ fontSize: 10, color: "#64748b" }}>req:{ev.total_requests} fallbacks:{ev.total_fallbacks}</span>
                <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: "auto" }}>{new Date(ev.timestamp * 1000).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Task 11.4: Model routing logic panel */}
      {routingData && (
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <BarChart3 size={15} style={{ color: "#6366f1" }} />
            <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Model Routing Logic</h2>
          </div>
          <p style={{ fontSize: 12, color: "#64748b", margin: "0 0 16px" }}>{routingData.description}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {routingData.providers.map((rp, i) => (
              <div key={rp.provider} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: i === 0 ? "#f0fdf4" : "#f8fafc", borderRadius: 10, border: `1px solid ${i === 0 ? "#bbf7d0" : "#e2e8f0"}` }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", minWidth: 20 }}>#{i + 1}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: PROVIDER_COLORS[rp.provider] || "#6366f1", textTransform: "capitalize", minWidth: 100 }}>{rp.provider}</span>
                <span style={{ fontSize: 11, background: rp.circuit_state === "closed" ? "#dcfce7" : "#fee2e2", color: rp.circuit_state === "closed" ? "#16a34a" : "#dc2626", padding: "2px 8px", borderRadius: 99, fontWeight: 700 }}>{rp.circuit_state}</span>
                <span style={{ fontSize: 11, color: "#64748b", flex: 1 }}>{rp.fallback_condition}</span>
                <span style={{ fontSize: 12, fontWeight: 800, color: rp.score >= 70 ? "#10b981" : rp.score >= 40 ? "#f59e0b" : "#ef4444" }}>Score: {Math.round(rp.score)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}
