"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Rocket, CheckCircle, XCircle, AlertTriangle, Loader2, RotateCcw, ArrowUpRight, Terminal, Shield } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Deployment = { id: string; project_id: string; environment: string; status: string; preview_url: string | null; triggered_by: string | null; created_at: string | null };
type DeploymentCheck = { id: string; check_type: string; status: string; message: string };

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  live:        { bg: "#dcfce7", color: "#16a34a" },
  building:    { bg: "#dbeafe", color: "#2563eb" },
  pending:     { bg: "#fef3c7", color: "#d97706" },
  failed:      { bg: "#fee2e2", color: "#dc2626" },
  rolled_back: { bg: "#f1f5f9", color: "#64748b" },
};

const CHECK_ICONS: Record<string, React.ReactNode> = {
  pass: <CheckCircle size={14} color="#10b981" />,
  warn: <AlertTriangle size={14} color="#f59e0b" />,
  fail: <XCircle size={14} color="#ef4444" />,
};

export default function DeployPage() {
  const params = useParams();
  const projectId = params?.project_id as string;

  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [checks, setChecks] = useState<DeploymentCheck[]>([]);
  const [buildLog, setBuildLog] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [deploying, setDeploying] = useState(false);
  const [promoting, setPromoting] = useState<string | null>(null);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [runningChecks, setRunningChecks] = useState<string | null>(null);
  const [confirmRollback, setConfirmRollback] = useState<Deployment | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";

  useEffect(() => { if (projectId) load(); }, [projectId]);
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [buildLog]);

  async function load() {
    setLoading(true);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/deployments/project/${projectId}`, { headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) setDeployments(await r.json());
    } catch {}
    finally { setLoading(false); }
  }

  async function createPreview() {
    setDeploying(true); setBuildLog([]);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/deployments/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ project_id: projectId }),
      });
      if (!r.ok) throw new Error("Deploy failed");
      const dep: Deployment = await r.json();
      setDeployments(prev => [dep, ...prev]);
      // Stream build log
      streamLog(dep.id, tok);
    } catch (e: any) {
      setBuildLog(prev => [...prev, `Error: ${e.message}`]);
    } finally { setDeploying(false); }
  }

  function streamLog(deploymentId: string, tok: string) {
    const es = new EventSource(`${API_URL}/deployments/${deploymentId}/log?token=${tok}`);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.line) setBuildLog(prev => [...prev, data.line]);
        if (data.done) { es.close(); load(); }
      } catch {}
    };
    es.onerror = () => es.close();
  }

  async function promote(deploymentId: string) {
    setPromoting(deploymentId);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/deployments/${deploymentId}/promote`, { method: "POST", headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) await load();
    } catch {}
    finally { setPromoting(null); }
  }

  async function rollback(dep: Deployment) {
    setConfirmRollback(null);
    setRollingBack(dep.id);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/deployments/${dep.id}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ project_id: projectId }),
      });
      if (r.ok) await load();
    } catch {}
    finally { setRollingBack(null); }
  }

  async function runChecks(deploymentId: string) {
    setRunningChecks(deploymentId); setChecks([]);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/deployments/${deploymentId}/checks`, { headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) setChecks(await r.json());
    } catch {}
    finally { setRunningChecks(null); }
  }

  const liveDeployment = deployments.find(d => d.status === "live" && d.environment === "production");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <Rocket size={24} style={{ color: "#6366f1" }} /> Deployments
          </h1>
          <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Manage preview and production deployments.</p>
        </div>
        <button onClick={createPreview} disabled={deploying}
          style={{ display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 12, padding: "11px 20px", fontSize: 14, fontWeight: 700, cursor: deploying ? "not-allowed" : "pointer", fontFamily: "inherit", opacity: deploying ? 0.7 : 1 }}>
          {deploying ? <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Rocket size={16} />}
          {deploying ? "Deploying..." : "Deploy Preview"}
        </button>
      </div>

      {/* Live production banner */}
      {liveDeployment && (
        <div style={{ background: "linear-gradient(135deg,#0f172a,#1e1b4b)", borderRadius: 18, padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
            <div>
              <p style={{ fontSize: 14, fontWeight: 800, color: "#fff", margin: 0 }}>Production Live</p>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", margin: "2px 0 0" }}>Deployed {liveDeployment.created_at ? new Date(liveDeployment.created_at).toLocaleString() : "recently"}</p>
            </div>
          </div>
          {liveDeployment.preview_url && (
            <a href={liveDeployment.preview_url} target="_blank" rel="noopener noreferrer"
              style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.8)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 10, padding: "8px 14px", fontSize: 13, fontWeight: 600, textDecoration: "none" }}>
              <ArrowUpRight size={14} /> View Live
            </a>
          )}
        </div>
      )}

      {/* Build log */}
      {buildLog.length > 0 && (
        <div style={{ background: "#0f172a", borderRadius: 16, border: "1px solid rgba(255,255,255,0.08)", overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", gap: 8 }}>
            <Terminal size={14} color="#818cf8" />
            <span style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.7)" }}>Build Log</span>
          </div>
          <div ref={logRef} style={{ padding: "12px 16px", maxHeight: 200, overflowY: "auto", fontFamily: "monospace", fontSize: 12, lineHeight: 1.6 }}>
            {buildLog.map((line, i) => (
              <div key={i} style={{ color: line.startsWith("Error") ? "#f87171" : "rgba(255,255,255,0.7)" }}>{line}</div>
            ))}
          </div>
        </div>
      )}

      {/* AI Checks */}
      {checks.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 8 }}>
            <Shield size={14} style={{ color: "#6366f1" }} />
            <span style={{ fontSize: 13, fontWeight: 800, color: "#0f172a" }}>AI Pre-Deploy Checks</span>
          </div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            {checks.map(c => (
              <div key={c.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", background: "#f8fafc", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                {CHECK_ICONS[c.status] || CHECK_ICONS.pass}
                <div>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#0f172a", textTransform: "capitalize" }}>{c.check_type.replace("_", " ")}</span>
                  <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>{c.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deployment history */}
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #f1f5f9" }}>
          <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Deployment History</h2>
        </div>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>
            <Loader2 size={24} style={{ color: "#cbd5e1", animation: "spin 1s linear infinite" }} />
          </div>
        ) : deployments.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 20px" }}>
            <Rocket size={32} style={{ color: "#cbd5e1", margin: "0 auto 10px" }} />
            <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>No deployments yet. Click Deploy Preview to start.</p>
          </div>
        ) : (
          <div>
            {deployments.map(dep => {
              const sc = STATUS_COLORS[dep.status] || STATUS_COLORS.pending;
              return (
                <div key={dep.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderBottom: "1px solid #f8fafc", flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, background: sc.bg, color: sc.color, padding: "2px 8px", borderRadius: 99 }}>{dep.status}</span>
                      <span style={{ fontSize: 11, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 99 }}>{dep.environment}</span>
                    </div>
                    <p style={{ fontSize: 11, color: "#94a3b8", margin: 0 }}>
                      {dep.created_at ? new Date(dep.created_at).toLocaleString() : "—"}
                      {dep.preview_url && (
                        <a href={dep.preview_url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8, color: "#6366f1", textDecoration: "none" }}>
                          {dep.preview_url.slice(0, 40)}...
                        </a>
                      )}
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    {dep.status === "live" && dep.environment === "preview" && (
                      <button onClick={() => promote(dep.id)} disabled={promoting === dep.id}
                        style={{ display: "flex", alignItems: "center", gap: 5, background: "#ede9fe", color: "#6366f1", border: "1px solid #c4b5fd", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: promoting === dep.id ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                        {promoting === dep.id ? <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> : <Rocket size={11} />}
                        Promote
                      </button>
                    )}
                    <button onClick={() => runChecks(dep.id)} disabled={runningChecks === dep.id}
                      style={{ display: "flex", alignItems: "center", gap: 5, background: "#f8fafc", color: "#64748b", border: "1px solid #e2e8f0", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 600, cursor: runningChecks === dep.id ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                      {runningChecks === dep.id ? <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> : <Shield size={11} />}
                      Checks
                    </button>
                    {dep.status !== "live" && (
                      <button onClick={() => setConfirmRollback(dep)} disabled={rollingBack === dep.id}
                        style={{ display: "flex", alignItems: "center", gap: 5, background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: rollingBack === dep.id ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                        {rollingBack === dep.id ? <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> : <RotateCcw size={11} />}
                        Rollback
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Rollback confirmation dialog */}
      {confirmRollback && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#fff", borderRadius: 18, padding: "28px 32px", maxWidth: 420, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: "0 0 10px" }}>Confirm Rollback</h3>
            <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 20px", lineHeight: 1.6 }}>
              This will restore the deployment from{" "}
              <strong>{confirmRollback.created_at ? new Date(confirmRollback.created_at).toLocaleString() : "unknown time"}</strong>{" "}
              ({confirmRollback.status}) as the new production deployment.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => rollback(confirmRollback)}
                style={{ flex: 1, background: "#dc2626", color: "#fff", border: "none", borderRadius: 10, padding: "11px", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                Confirm Rollback
              </button>
              <button onClick={() => setConfirmRollback(null)}
                style={{ flex: 1, background: "#f8fafc", color: "#374151", border: "1px solid #e2e8f0", borderRadius: 10, padding: "11px", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
