"use client";
import { Monitor, X } from "lucide-react";

interface VpsRequiredModalProps {
  open: boolean;
  onClose: () => void;
  feature: string;
}

export default function VpsRequiredModal({ open, onClose, feature }: VpsRequiredModalProps) {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: 480, width: "100%",
          background: "#fff", borderRadius: 20,
          boxShadow: "0 25px 60px rgba(0,0,0,0.25)",
          padding: "32px 28px 28px",
          position: "relative",
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 14, right: 14,
            background: "#f1f5f9", border: "none", borderRadius: "50%",
            width: 32, height: 32, display: "flex", alignItems: "center",
            justifyContent: "center", cursor: "pointer", color: "#64748b",
          }}
        >
          <X size={16} />
        </button>

        <div
          style={{
            width: 56, height: 56, borderRadius: 16,
            background: "linear-gradient(135deg, #f59e0b, #d97706)",
            display: "flex", alignItems: "center", justifyContent: "center",
            marginBottom: 18,
          }}
        >
          <Monitor size={28} color="#fff" />
        </div>

        <h2 style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>
          VPS Required
        </h2>
        <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 4px", lineHeight: 1.6 }}>
          <strong>{feature}</strong> requires a full VPS deployment with Playwright browser automation, a Redis broker, and a Celery worker.
        </p>
        <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 20px", lineHeight: 1.6 }}>
          Watch a demo video to see it in action, or deploy the full stack to your own server.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <a
            href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff",
              fontWeight: 700, fontSize: 14, padding: "12px", borderRadius: 12,
              border: "none", cursor: "pointer", textDecoration: "none",
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
            Watch Demo Video
          </a>
          <a
            href="https://github.com/anomalyco/AI-Business-Builder#deployment"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: "#f1f5f9", color: "#0f172a",
              fontWeight: 600, fontSize: 14, padding: "12px", borderRadius: 12,
              border: "none", cursor: "pointer", textDecoration: "none",
            }}
          >
            View VPS Deployment Guide
          </a>
        </div>

        <p style={{ fontSize: 12, color: "#94a3b8", margin: "16px 0 0", textAlign: "center" }}>
          This feature is available on the Render Free plan
        </p>
      </div>
    </div>
  );
}
