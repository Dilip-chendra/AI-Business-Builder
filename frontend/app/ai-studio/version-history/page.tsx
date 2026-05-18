"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  GitCompareArrows,
  History,
  Loader2,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useActiveContext } from "@/lib/active-context";
import { api } from "@/lib/api";
import type { StudioVersionRecord } from "@/lib/types";
import { cleanDisplayText, truncateClean } from "@/lib/text";
import { useToast } from "@/components/Toast";

export default function AIStudioVersionHistoryPage() {
  const { active, businesses } = useActiveContext();
  const toast = useToast();
  const [history, setHistory] = useState<StudioVersionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [compareBaseId, setCompareBaseId] = useState<string | null>(null);

  const businessId = active.business_id || businesses[0]?.id || "";
  const businessName = useMemo(
    () => businesses.find((item) => item.id === businessId)?.name || "Active business",
    [businessId, businesses]
  );

  const loadHistory = async () => {
    if (!businessId) {
      setHistory([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const rows = await api.listStudioHistory(businessId);
      setHistory(rows);
    } catch (error: any) {
      toast.error(error.message || "Could not load version history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [businessId]);

  const handleRestore = async (versionId: string) => {
    if (!businessId) return;
    setRestoringId(versionId);
    try {
      await api.revertStudioVersion(versionId, businessId);
      toast.success("Version restored into the active project workspace.");
      await loadHistory();
    } catch (error: any) {
      toast.error(error.message || "Could not restore this version.");
    } finally {
      setRestoringId(null);
    }
  };

  const handleDelete = async (versionId: string) => {
    setDeletingId(versionId);
    try {
      await api.deleteStudioVersion(versionId);
      setHistory((current) => current.filter((item) => item.id !== versionId));
      toast.success("Version removed from history.");
    } catch (error: any) {
      toast.error(error.message || "Could not delete this version.");
    } finally {
      setDeletingId(null);
    }
  };

  const compareTarget = compareBaseId ? history.find((entry) => entry.id === compareBaseId) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <section
        style={{
          borderRadius: 28,
          padding: "28px 30px",
          background: "linear-gradient(135deg, #020617 0%, #111827 48%, #1f1b4d 100%)",
          color: "#fff",
          border: "1px solid rgba(148,163,184,0.14)",
          boxShadow: "0 30px 80px rgba(15,23,42,0.22)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Link href="/ai-studio" style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "rgba(255,255,255,0.75)", textDecoration: "none", fontSize: 13, fontWeight: 600 }}>
              <ArrowLeft size={14} />
              Back to AI Studio
            </Link>
            <div>
              <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", color: "rgba(255,255,255,0.55)", textTransform: "uppercase" }}>
                Version History
              </p>
              <h1 style={{ margin: 0, fontSize: 34, lineHeight: 1.05, letterSpacing: "-0.03em" }}>Change history for {businessName}</h1>
            </div>
            <p style={{ margin: 0, maxWidth: 760, color: "rgba(255,255,255,0.72)", lineHeight: 1.7, fontSize: 14 }}>
              Review the prompts, snapshots, and restore points that shaped this project. The history stays out of the main studio now, so the editing workspace can stay calm and focused.
            </p>
          </div>
          <button
            onClick={loadHistory}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid rgba(255,255,255,0.16)",
              background: "rgba(255,255,255,0.06)",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </section>

      {compareTarget && (
        <section style={{ borderRadius: 24, background: "#fff", border: "1px solid #e2e8f0", padding: 24, boxShadow: "0 16px 44px rgba(15,23,42,0.06)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 }}>
            <div>
              <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 800, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Compare Snapshot
              </p>
              <h2 style={{ margin: 0, fontSize: 20, color: "#0f172a" }}>{compareTarget.file_path}</h2>
            </div>
            <button onClick={() => setCompareBaseId(null)} style={{ border: "none", background: "#eef2ff", color: "#4338ca", borderRadius: 12, padding: "10px 12px", cursor: "pointer", fontWeight: 700 }}>
              Close Compare
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <div style={{ borderRadius: 18, border: "1px solid #e2e8f0", background: "#f8fafc", padding: 18 }}>
              <p style={{ margin: "0 0 10px", fontSize: 12, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>Prompt</p>
              <p style={{ margin: 0, color: "#334155", lineHeight: 1.7 }}>{cleanDisplayText(compareTarget.instruction || compareTarget.source || "No prompt stored")}</p>
            </div>
            <div style={{ borderRadius: 18, border: "1px solid #e2e8f0", background: "#fff", padding: 18 }}>
              <p style={{ margin: "0 0 10px", fontSize: 12, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>Output Preview</p>
              <div style={{ whiteSpace: "pre-wrap", color: "#0f172a", lineHeight: 1.8, fontSize: 14 }}>
                {cleanDisplayText(compareTarget.content_preview)}
              </div>
            </div>
          </div>
        </section>
      )}

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "100px 0" }}>
          <Loader2 size={34} style={{ color: "#6366f1", animation: "spin 1s linear infinite" }} />
          <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
        </div>
      ) : history.length === 0 ? (
        <div style={{ borderRadius: 24, background: "#fff", border: "1px solid #e2e8f0", padding: 40, textAlign: "center", color: "#475569" }}>
          <History size={28} style={{ color: "#6366f1", margin: "0 auto 12px" }} />
          <h2 style={{ margin: "0 0 8px", fontSize: 22, color: "#0f172a" }}>No saved versions yet</h2>
          <p style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.7 }}>
            Once AI Studio and the code workspace create tracked file changes, they will appear here with restore and compare controls.
          </p>
          <Link href="/ai-studio" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 14, textDecoration: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700 }}>
            Return to AI Studio
          </Link>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 22 }}>
          {history.map((version, index) => {
            const latest = index === 0;
            return (
              <article key={version.id} style={{ display: "flex", flexDirection: "column", gap: 18, borderRadius: 26, padding: 22, background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)", border: latest ? "1px solid #c7d2fe" : "1px solid #e2e8f0", boxShadow: latest ? "0 24px 60px rgba(99,102,241,0.12)" : "0 20px 60px rgba(15,23,42,0.08)" }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 800, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Version {version.version_number}
                    </p>
                    <h2 style={{ margin: 0, fontSize: 19, lineHeight: 1.3, color: "#0f172a" }}>{cleanDisplayText(version.file_path)}</h2>
                  </div>
                  <span style={{ padding: "7px 10px", borderRadius: 999, background: latest ? "#ede9fe" : "#e2e8f0", color: latest ? "#6d28d9" : "#475569", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0 }}>
                    {latest ? "Latest" : cleanDisplayText(version.source || "saved")}
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                  <div style={{ borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                    <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Prompt Used</p>
                    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "#334155" }}>{truncateClean(cleanDisplayText(version.instruction || version.source || "No prompt stored"), 150)}</p>
                  </div>
                  <div style={{ borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0", padding: "12px 14px" }}>
                    <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>Created</p>
                    <p style={{ margin: "0 0 6px", fontSize: 13, lineHeight: 1.6, color: "#0f172a", fontWeight: 700 }}>
                      {version.created_at ? new Date(version.created_at).toLocaleString() : "Unknown"}
                    </p>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "#64748b" }}>
                      <Clock3 size={13} />
                      {latest ? "Current active candidate" : "Available restore point"}
                    </span>
                  </div>
                </div>

                <div style={{ borderRadius: 20, background: "#fff", border: "1px solid #e2e8f0", padding: 18 }}>
                  <p style={{ margin: "0 0 10px", fontSize: 12, fontWeight: 800, color: "#0f172a", textTransform: "uppercase", letterSpacing: "0.08em" }}>Generated Output Preview</p>
                  <div style={{ whiteSpace: "pre-wrap", color: "#334155", fontSize: 14, lineHeight: 1.8 }}>
                    {truncateClean(cleanDisplayText(version.content_preview), 420)}
                  </div>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: "auto" }}>
                  <button onClick={() => handleRestore(version.id)} disabled={!businessId || restoringId === version.id} style={actionButton("#eef2ff", "#4338ca")}>
                    {restoringId === version.id ? <Loader2 size={14} /> : <RotateCcw size={14} />}
                    Restore Version
                  </button>
                  <button onClick={() => setCompareBaseId(version.id)} style={actionButton("#f8fafc", "#0f172a")}>
                    <GitCompareArrows size={14} />
                    Compare Version
                  </button>
                  <button onClick={() => handleDelete(version.id)} disabled={deletingId === version.id} style={actionButton("#fee2e2", "#b91c1c")}>
                    {deletingId === version.id ? <Loader2 size={14} /> : <Trash2 size={14} />}
                    Delete Version
                  </button>
                  {latest && (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "10px 14px", borderRadius: 14, background: "#dcfce7", color: "#15803d", fontSize: 13, fontWeight: 700 }}>
                      <CheckCircle2 size={14} />
                      Current active line
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function actionButton(background: string, color: string): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: 14,
    border: "none",
    background,
    color,
    cursor: "pointer",
    fontWeight: 700,
    fontSize: 13,
  };
}
