"use client";
import { X, Lock, Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";

interface FeatureGateModalProps {
  feature: string;
  featureLabel: string;
  requiredTier: string;
  currentTier: string;
  onClose: () => void;
}

export function FeatureGateModal({
  feature,
  featureLabel,
  requiredTier,
  currentTier,
  onClose,
}: FeatureGateModalProps) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center",
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff", borderRadius: 20, padding: "32px",
          maxWidth: 440, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
          position: "relative",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close */}
        <button
          onClick={onClose}
          style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", color: "#94a3b8", padding: 4, display: "flex", alignItems: "center" }}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        {/* Icon */}
        <div style={{ width: 56, height: 56, borderRadius: 16, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20, boxShadow: "0 8px 24px rgba(99,102,241,0.35)" }}>
          <Lock size={24} color="#fff" />
        </div>

        {/* Content */}
        <h2 style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", margin: "0 0 8px" }}>
          Upgrade to {requiredTier}
        </h2>
        <p style={{ fontSize: 14, color: "#64748b", margin: "0 0 20px", lineHeight: 1.6 }}>
          <strong style={{ color: "#0f172a" }}>{featureLabel}</strong> is available on the{" "}
          <strong style={{ color: "#6366f1" }}>{requiredTier}</strong> plan and above.
          You are currently on the <strong>{currentTier}</strong> plan.
        </p>

        {/* Benefits */}
        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 16px", marginBottom: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 10px" }}>
            {requiredTier} includes
          </p>
          {[
            "Unlimited AI generations",
            "AI Studio multi-step generation",
            "AI Code Editor with RAG search",
            "Deployment system",
            "Team workspace collaboration",
          ].map(benefit => (
            <div key={benefit} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <Sparkles size={12} color="#6366f1" />
              <span style={{ fontSize: 13, color: "#374151" }}>{benefit}</span>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div style={{ display: "flex", gap: 10 }}>
          <Link
            href="/settings"
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff",
              border: "none", borderRadius: 12, padding: "12px", fontSize: 14, fontWeight: 700,
              textDecoration: "none", boxShadow: "0 4px 16px rgba(99,102,241,0.35)",
            }}
            onClick={onClose}
          >
            Upgrade Now <ArrowRight size={16} />
          </Link>
          <button
            onClick={onClose}
            style={{ padding: "12px 18px", background: "#f8fafc", color: "#64748b", border: "1px solid #e2e8f0", borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
