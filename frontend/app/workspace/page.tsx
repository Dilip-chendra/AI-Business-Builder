"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, Plus, Loader2, Users, FolderOpen, Settings } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Workspace = { id: string; name: string; slug: string; owner_id: string; created_at: string | null };
type Project = { id: string; name: string; type: string; created_at: string | null };

export default function WorkspacePage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newProjName, setNewProjName] = useState("");
  const [newProjType, setNewProjType] = useState("business");

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const tok = getToken();
    if (!tok) { setLoading(false); return; }
    try {
      const r = await fetch(`${API_URL}/workspaces`, { headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) {
        const list: Workspace[] = await r.json();
        setWorkspaces(list);
        if (list.length > 0) { setSelected(list[0]); await loadProjects(list[0].id); }
      }
    } catch {}
    finally { setLoading(false); }
  }

  async function loadProjects(wsId: string) {
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/workspaces/${wsId}/projects`, { headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) setProjects(await r.json());
    } catch {}
  }

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreating(true);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ name: newWsName.trim() }),
      });
      if (r.ok) { setNewWsName(""); await load(); }
    } catch {}
    finally { setCreating(false); }
  }

  async function createProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newProjName.trim() || !selected) return;
    setCreating(true);
    const tok = getToken();
    try {
      const r = await fetch(`${API_URL}/workspaces/${selected.id}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({ name: newProjName.trim(), type: newProjType }),
      });
      if (r.ok) { setNewProjName(""); await loadProjects(selected.id); }
    } catch {}
    finally { setCreating(false); }
  }

  const inputStyle: React.CSSProperties = { width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit", boxSizing: "border-box" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Building2 size={24} style={{ color: "#6366f1" }} /> Workspaces
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Manage your workspaces and projects.</p>
      </div>

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
          <Loader2 size={28} style={{ color: "#cbd5e1", animation: "spin 1s linear infinite" }} />
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20, alignItems: "start" }}>
          {/* Workspace list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px" }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", margin: "0 0 14px" }}>Your Workspaces</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 14 }}>
                {workspaces.map(ws => (
                  <button key={ws.id} onClick={() => { setSelected(ws); loadProjects(ws.id); }}
                    style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 10, border: `1.5px solid ${selected?.id === ws.id ? "#6366f1" : "#e2e8f0"}`, background: selected?.id === ws.id ? "#ede9fe" : "#f8fafc", cursor: "pointer", fontFamily: "inherit", textAlign: "left" }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: 11, flexShrink: 0 }}>
                      {ws.name[0]?.toUpperCase()}
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 600, color: selected?.id === ws.id ? "#6366f1" : "#0f172a" }}>{ws.name}</span>
                  </button>
                ))}
              </div>
              <form onSubmit={createWorkspace} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input required placeholder="New workspace name" value={newWsName} onChange={e => setNewWsName(e.target.value)} style={inputStyle} />
                <button type="submit" disabled={creating} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "9px", fontSize: 13, fontWeight: 700, cursor: creating ? "not-allowed" : "pointer", fontFamily: "inherit" }}>
                  <Plus size={14} /> Create Workspace
                </button>
              </form>
            </div>
          </div>

          {/* Projects */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {selected && (
              <>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>{selected.name} — Projects</h2>
                  <Link href={`/workspace/${selected.slug}/settings`} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#64748b", textDecoration: "none" }}>
                    <Settings size={13} /> Settings
                  </Link>
                </div>
                <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: "20px" }}>
                  <form onSubmit={createProject} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                    <input required placeholder="Project name" value={newProjName} onChange={e => setNewProjName(e.target.value)} style={{ ...inputStyle, flex: 1 }} />
                    <select value={newProjType} onChange={e => setNewProjType(e.target.value)} style={{ ...inputStyle, width: "auto" }}>
                      <option value="business">Business</option>
                      <option value="codebase">Codebase</option>
                    </select>
                    <button type="submit" disabled={creating} style={{ display: "flex", alignItems: "center", gap: 5, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "9px 16px", fontSize: 13, fontWeight: 700, cursor: creating ? "not-allowed" : "pointer", fontFamily: "inherit", whiteSpace: "nowrap" }}>
                      <Plus size={14} /> Add
                    </button>
                  </form>
                  {projects.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "40px 20px" }}>
                      <FolderOpen size={32} style={{ color: "#cbd5e1", margin: "0 auto 10px" }} />
                      <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>No projects yet. Create one above.</p>
                    </div>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
                      {projects.map(p => (
                        <Link key={p.id} href={`/workspace/${selected.slug}/project/${p.id}`} style={{ textDecoration: "none" }}>
                          <div style={{ background: "#f8fafc", borderRadius: 14, border: "1px solid #e2e8f0", padding: "16px", cursor: "pointer", transition: "border-color 0.15s" }}
                            onMouseEnter={e => (e.currentTarget.style.borderColor = "#6366f1")}
                            onMouseLeave={e => (e.currentTarget.style.borderColor = "#e2e8f0")}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                              <FolderOpen size={16} style={{ color: "#6366f1" }} />
                              <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>{p.name}</span>
                            </div>
                            <span style={{ fontSize: 11, background: p.type === "business" ? "#ede9fe" : "#dbeafe", color: p.type === "business" ? "#7c3aed" : "#2563eb", padding: "2px 8px", borderRadius: 99, fontWeight: 600 }}>{p.type}</span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
