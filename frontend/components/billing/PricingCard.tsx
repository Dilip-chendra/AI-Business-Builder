"use client";

import { Check, Loader2 } from "lucide-react";

import type { BillingPlan } from "@/lib/types";

type PricingCardProps = {
  plan: BillingPlan;
  currentPlanSlug?: string;
  onSubscribe: (slug: string) => Promise<void>;
  busySlug?: string | null;
};

export function PricingCard({ plan, currentPlanSlug, onSubscribe, busySlug }: PricingCardProps) {
  const highlights = Array.isArray(plan.features_json?.highlights) ? plan.features_json.highlights as string[] : [];
  const isCurrent = plan.slug === currentPlanSlug;
  const isFree = plan.slug === "free";
  return (
    <div
      style={{
        background: isCurrent ? "linear-gradient(180deg, rgba(99,102,241,0.18), rgba(15,23,42,0.95))" : "#0f172a",
        border: isCurrent ? "1.5px solid rgba(129,140,248,0.7)" : "1px solid rgba(255,255,255,0.08)",
        borderRadius: 18,
        padding: 24,
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        gap: 18,
        minHeight: 360,
      }}
    >
      <div>
        <div style={{ fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", color: isCurrent ? "#c4b5fd" : "rgba(255,255,255,0.45)", marginBottom: 8 }}>
          {plan.interval === "free" ? "Starter" : plan.interval === "year" ? "Yearly" : "Monthly"}
        </div>
        <h3 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>{plan.name}</h3>
        <p style={{ color: "rgba(255,255,255,0.6)", lineHeight: 1.6, margin: "8px 0 0" }}>{plan.description}</p>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontSize: 36, fontWeight: 900 }}>
          {plan.price_cents === 0 ? "$0" : `$${(plan.price_cents / 100).toFixed(0)}`}
        </span>
        <span style={{ color: "rgba(255,255,255,0.55)", fontSize: 13 }}>
          {isFree ? "/ forever" : plan.interval === "year" ? "/ year" : "/ month"}
        </span>
      </div>

      <button
        onClick={() => onSubscribe(plan.slug)}
        disabled={isCurrent || isFree || busySlug === plan.slug}
        style={{
          border: "none",
          borderRadius: 12,
          padding: "12px 16px",
          fontWeight: 800,
          fontSize: 14,
          cursor: isCurrent || isFree || busySlug === plan.slug ? "not-allowed" : "pointer",
          background: isCurrent ? "rgba(255,255,255,0.08)" : "linear-gradient(135deg,#6366f1,#8b5cf6)",
          color: "#fff",
          opacity: isCurrent || isFree ? 0.8 : 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
      >
        {busySlug === plan.slug ? <Loader2 size={15} className="animate-spin" /> : null}
        {isCurrent ? "Current Plan" : isFree ? "Included" : "Subscribe with PayPal"}
      </button>

      <div style={{ display: "grid", gap: 10 }}>
        {highlights.map((item) => (
          <div key={item} style={{ display: "flex", gap: 10, alignItems: "flex-start", color: "rgba(255,255,255,0.8)" }}>
            <Check size={15} style={{ color: "#34d399", flexShrink: 0, marginTop: 2 }} />
            <span style={{ lineHeight: 1.5, fontSize: 13 }}>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
