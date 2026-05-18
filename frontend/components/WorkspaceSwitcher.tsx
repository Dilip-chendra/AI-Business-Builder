"use client";

import { useEffect, useRef, useState } from "react";
import { Building2, Check, ChevronDown, Plus } from "lucide-react";

import { api } from "@/lib/api";
import { useActiveContext } from "@/lib/active-context";

export function WorkspaceSwitcher() {
  const {
    active,
    workspaces,
    activeWorkspace,
    isLoading,
    refresh,
    setActiveContext,
  } = useActiveContext();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  async function createWorkspace() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const ws = await api.createWorkspace({ name: newName.trim() });
      await setActiveContext({ workspace_id: ws.id, business_id: null, project_id: null });
      await refresh();
      setNewName("");
      setOpen(false);
    } finally {
      setCreating(false);
    }
  }

  const displayName = activeWorkspace?.name || (isLoading ? "Loading workspace..." : "Create workspace");

  return (
    <div ref={ref} style={{ padding: "10px 10px 4px", position: "relative" }}>
      <button
        onClick={() => setOpen((value) => !value)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "8px 10px",
          borderRadius: 8,
          background: "rgba(255,255,255,0.07)",
          border: "1px solid rgba(255,255,255,0.08)",
          cursor: "pointer",
          textAlign: "left",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.11)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.07)")}
        aria-label="Switch workspace"
        aria-expanded={open}
      >
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            flexShrink: 0,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontWeight: 700,
            fontSize: 10,
          }}
        >
          {displayName[0]?.toUpperCase() || "W"}
        </div>
        <span
          style={{
            flex: 1,
            color: "rgba(255,255,255,0.85)",
            fontSize: 13,
            fontWeight: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {displayName}
        </span>
        <ChevronDown
          size={14}
          style={{
            color: "rgba(255,255,255,0.4)",
            flexShrink: 0,
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 0.2s",
          }}
        />
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% - 4px)",
            left: 10,
            right: 10,
            background: "#1e293b",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 10,
            zIndex: 200,
            overflow: "hidden",
            boxShadow: "0 8px 30px rgba(0,0,0,0.4)",
          }}
        >
          {workspaces.length > 0 && (
            <div style={{ padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={async () => {
                    await setActiveContext({ workspace_id: ws.id, business_id: null, project_id: null });
                    setOpen(false);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    padding: "8px 12px",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    color: "rgba(255,255,255,0.8)",
                    fontSize: 13,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  <Building2 size={13} color="#818cf8" />
                  <span style={{ flex: 1, textAlign: "left" }}>{ws.name}</span>
                  {active.workspace_id === ws.id && <Check size={12} color="#10b981" />}
                </button>
              ))}
            </div>
          )}
          <div style={{ padding: "8px" }}>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") createWorkspace().catch(console.error);
                }}
                placeholder="New workspace name"
                style={{
                  flex: 1,
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 7,
                  padding: "6px 10px",
                  fontSize: 12,
                  color: "#e2e8f0",
                  outline: "none",
                  fontFamily: "inherit",
                }}
              />
              <button
                onClick={() => createWorkspace().catch(console.error)}
                disabled={creating || !newName.trim()}
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 7,
                  border: "none",
                  background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
                  color: "#fff",
                  cursor: creating || !newName.trim() ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  opacity: creating || !newName.trim() ? 0.5 : 1,
                  flexShrink: 0,
                }}
                aria-label="Create workspace"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
