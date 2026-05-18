"use client";

import Link from "next/link";
import { BriefcaseBusiness, FolderKanban, ChevronDown, Plus } from "lucide-react";

import { useActiveContext } from "@/lib/active-context";

export function BusinessProjectSwitcher() {
  const {
    active,
    businesses,
    projects,
    activeBusiness,
    activeProject,
    isLoading,
    setActiveContext,
  } = useActiveContext();

  if (isLoading) {
    return (
      <div style={{ padding: "0 10px 10px" }}>
        <div style={{ height: 92, borderRadius: 12, background: "rgba(255,255,255,0.05)" }} />
      </div>
    );
  }

  if (!businesses.length) {
    return (
      <div style={{ padding: "0 10px 10px" }}>
        <div
          style={{
            borderRadius: 12,
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(255,255,255,0.04)",
            padding: 12,
            display: "grid",
            gap: 10,
          }}
        >
          <div>
            <div style={{ color: "rgba(255,255,255,0.75)", fontSize: 12, fontWeight: 700 }}>Business Context</div>
            <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 11, marginTop: 4 }}>
              Create your first business to unlock products, marketing, analytics, and AI Studio.
            </div>
          </div>
          <Link
            href="/generator"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              textDecoration: "none",
              borderRadius: 10,
              padding: "9px 12px",
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              color: "#fff",
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            <Plus size={13} />
            Create Business
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "0 10px 10px" }}>
      <div
        style={{
          borderRadius: 12,
          border: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(255,255,255,0.04)",
          padding: 12,
          display: "grid",
          gap: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div>
            <div style={{ color: "rgba(255,255,255,0.78)", fontSize: 12, fontWeight: 700 }}>Active Context</div>
            <div style={{ color: "rgba(255,255,255,0.42)", fontSize: 11, marginTop: 2 }}>
              Everything below follows this business and project.
            </div>
          </div>
          <Link
            href="/workspace"
            style={{
              color: "#a5b4fc",
              fontSize: 11,
              fontWeight: 700,
              textDecoration: "none",
            }}
          >
            Open Workspace
          </Link>
        </div>

        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ color: "rgba(255,255,255,0.48)", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Business
          </span>
          <div style={{ position: "relative" }}>
            <BriefcaseBusiness size={13} style={{ position: "absolute", left: 10, top: 10, color: "rgba(255,255,255,0.45)" }} />
            <select
              value={active.business_id ?? ""}
              onChange={async (event) => {
                const nextBusinessId = event.target.value || null;
                const matching = businesses.find((item) => item.id === nextBusinessId) || null;
                await setActiveContext({
                  business_id: nextBusinessId,
                  project_id: matching?.project_id ?? active.project_id ?? null,
                });
              }}
              style={{
                width: "100%",
                appearance: "none",
                background: "rgba(15,23,42,0.9)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 10,
                color: "#e2e8f0",
                fontSize: 12,
                padding: "8px 32px 8px 32px",
                outline: "none",
                fontFamily: "inherit",
              }}
            >
              {businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
            <ChevronDown size={13} style={{ position: "absolute", right: 10, top: 10, color: "rgba(255,255,255,0.35)" }} />
          </div>
        </label>

        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ color: "rgba(255,255,255,0.48)", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Project
          </span>
          <div style={{ position: "relative" }}>
            <FolderKanban size={13} style={{ position: "absolute", left: 10, top: 10, color: "rgba(255,255,255,0.45)" }} />
            <select
              value={active.project_id ?? ""}
              onChange={(event) => setActiveContext({ project_id: event.target.value || null }).catch(console.error)}
              style={{
                width: "100%",
                appearance: "none",
                background: "rgba(15,23,42,0.9)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 10,
                color: "#e2e8f0",
                fontSize: 12,
                padding: "8px 32px 8px 32px",
                outline: "none",
                fontFamily: "inherit",
              }}
            >
              {projects.length === 0 ? <option value="">No projects yet</option> : null}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            <ChevronDown size={13} style={{ position: "absolute", right: 10, top: 10, color: "rgba(255,255,255,0.35)" }} />
          </div>
        </label>

        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ color: "rgba(255,255,255,0.82)", fontSize: 12, fontWeight: 600 }}>
            {activeBusiness?.name || "No business selected"}
          </div>
          <div style={{ color: "rgba(255,255,255,0.42)", fontSize: 11 }}>
            {activeProject?.name || "Choose a project to scope AI Studio, Code Editor, and analytics."}
          </div>
        </div>
      </div>
    </div>
  );
}
