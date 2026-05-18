"use client";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  headline: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  iconColor?: string;
}

export function EmptyState({ icon: Icon, headline, description, action, iconColor = "#cbd5e1" }: EmptyStateProps) {
  return (
    <div style={{
      borderRadius: 20,
      border: "2px dashed #e2e8f0",
      background: "#fff",
      padding: "56px 32px",
      textAlign: "center",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 8,
    }}>
      <div style={{
        width: 56,
        height: 56,
        borderRadius: 16,
        background: "#f8fafc",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 4,
      }}>
        <Icon size={28} style={{ color: iconColor }} aria-hidden="true" />
      </div>
      <h3 style={{ fontSize: 16, fontWeight: 700, color: "#374151", margin: 0 }}>{headline}</h3>
      <p style={{ fontSize: 13, color: "#94a3b8", margin: 0, maxWidth: 320, lineHeight: 1.6 }}>{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          style={{
            marginTop: 8,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "10px 20px",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
