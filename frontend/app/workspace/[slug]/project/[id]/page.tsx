"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FolderOpen, Loader2, Plus, Trash2, Eye, EyeOff, ArrowLeft } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Project = { id: string; name: string; type: string; workspace_id: string; created_at: string | null };
type EnvVar = { key: string; value: string };

export default function ProjectOverviewPage() {
  const params = useParams();
  const projectId = params?.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [showValues, setShowValues] = useState(false);
  const [saving, setSaving] = useState(false);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";

  useEffect(() => {
    if (!projectId) return;
    const tok = getToken();
    Promise.all([
      fetch(`${API_URL}/projects/${projectId}`, { headers: { Authorization: `Bearer ${tok}` } }),
      fetch(`${API_URL}/projects/${projectId}/envvars`, { headers: { Authorization: `Bearer ${tok}` } }),
    ]).then(async ([r1, r2]) => {
      if (r1.ok) setProject(await r1.json());
      if (r2.ok) setEnvVars(await r2.json());
    }).catch(() => {}).finally(() => setLoading(false));
  }, [projectId]);

  async function addEnvVar(e: React.FormEvent) {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim()) return;
    setSaving(true);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/projects/${projectId}/envvars`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ key: newKey.trim(), value: newValue.trim() }),
      });
      if (r.ok) {
        setEnvVars(prev => [...prev.filter(e => e.key !== newKey.trim()), { key: newKey.trim(), value: newValue.trim().slice(0, 4) + "****" }]);
        setNewKey(""); setNewValue("");
      }
    } catch {}
    finally { setSaving(false); }
  }

  async function deleteEnvVar(key: string) {
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/projects/${projectId}/envvars/${key}`, { method: "DELETE", headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) setEnvVars(prev => prev.filter(e => e.key !== key));
    } catch {}
  }

  const inputStyle: React.CSSProperties = { borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" };

  if (loading) return (
    <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
      <Loader2 size={28} style={{ color: "#cbd5e1", animation: "spin 1s linear infinite" }} />
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );

  if (!project) return (
    <div style={{ textAlign: "center", padding: "80px 20px" }}>
      <p style={{ fontSize: 16, color: "#64748b" }}>Project not found.</p>
      <Link href="/workspace" style={{ color: "#6366f1", textDecoration: "none", fontSize: 14 }}>Back to Workspaces</Link>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Link href="/workspace" style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "#64748b", textDecoration: "none" }}>
          <ArrowLeft size={14} /> Workspaces
        </Link>
        <span style={{ color: "#cbd5e1" }}>/</span>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <FolderOpen size={22} style={{ color: "#6366f1" }} /> {project.name}
        </h1>
        <span style={{ fontSize: 11, background: project.type === "business" ? "#ede9fe" : "#dbeafe", color: project.type === "business" ? "#7c3aed" : "#2563eb", padding: "3px 10px", borderRadius: 99, fontWeight: 700 }}>{project.type}</span>
      </div>

      {/* Quick actions */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {[
          { href: "/dashboard", label: "Dashboard" },
          { href: "/marketing", label: "Marketing" },
          { href: "/analytics", label: "Analytics" },
          { href: `/deploy/${project.id}`, label: "Deploy" },
        ].map(({ href, label }) => (
          <Link key={href} href={href} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, fontWeight: 600, color: "#6366f1", textDecoration: "none", padding: "7px 14px", borderRadius: 10, background: "#ede9fe", border: "1px solid #c4b5fd" }}>
            {label}
          </Link>
        ))}
      </div>

      {/* Environment Variables */}
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: 0 }}>Environment Variables</h2>
          <button onClick={() => setShowValues(v => !v)} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#64748b", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "5px 10px", cursor: "pointer", fontFamily: "inherit" }}>
            {showValues ? <EyeOff size={13} /> : <Eye size={13} />}
            {showValues ? "Hide values" : "Show values"}
          </button>
        </div>
        <div style={{ padding: "16px 20px" }}>
          <form onSubmit={addEnvVar} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input required placeholder="KEY" value={newKey} onChange={e => setNewKey(e.target.value)} style={{ ...inputStyle, flex: 1 }} />
            <input required placeholder="value" value={newValue} onChange={e => setNewValue(e.target.value)} type={showValues ? "text" : "password"} style={{ ...inputStyle, flex: 2 }} />
            <button type="submit" disabled={saving} style={{ display: "flex", alignItems: "center", gap: 5, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "9px 14px", fontSize: 13, fontWeight: 700, cursor: saving ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
              <Plus size={14} /> Add
            </button>
          </form>
          {envVars.length === 0 ? (
            <p style={{ fontSize: 13, color: "#94a3b8", textAlign: "center", padding: "20px 0" }}>No environment variables set.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {envVars.map(ev => (
                <div key={ev.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "#f8fafc", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                  <code style={{ fontSize: 12, fontWeight: 700, color: "#6366f1", minWidth: 120 }}>{ev.key}</code>
                  <code style={{ fontSize: 12, color: "#64748b", flex: 1, fontFamily: "monospace" }}>{showValues ? ev.value : "••••••••"}</code>
                  <button onClick={() => deleteEnvVar(ev.key)} style={{ background: "none", border: "none", cursor: "pointer", color: "#fca5a5", padding: 4, borderRadius: 6, display: "flex", alignItems: "center" }}
                    onMouseEnter={e => (e.currentTarget.style.color = "#ef4444")}
                    onMouseLeave={e => (e.currentTarget.style.color = "#fca5a5")}
                    aria-label={`Delete ${ev.key}`}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
