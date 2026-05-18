"use client";

import Link from "next/link";

export function UpgradeModal({
  open,
  title,
  description,
  onClose,
}: {
  open: boolean;
  title: string;
  description: string;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.7)",
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 520, borderRadius: 20, background: "#0f172a", padding: 28, color: "#fff" }}
      >
        <div style={{ fontSize: 22, fontWeight: 900, marginBottom: 10 }}>{title}</div>
        <p style={{ color: "rgba(255,255,255,0.65)", lineHeight: 1.7, margin: 0 }}>{description}</p>
        <div style={{ display: "flex", gap: 12, marginTop: 22 }}>
          <Link
            href="/pricing"
            style={{
              textDecoration: "none",
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              color: "#fff",
              fontWeight: 800,
              borderRadius: 12,
              padding: "12px 16px",
            }}
          >
            View Plans
          </Link>
          <button
            onClick={onClose}
            style={{
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 12,
              padding: "12px 16px",
              background: "transparent",
              color: "#cbd5e1",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
