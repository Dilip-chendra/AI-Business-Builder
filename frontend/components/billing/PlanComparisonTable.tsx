"use client";

import type { BillingPlan } from "@/lib/types";

const FEATURES = [
  "ai_request",
  "browser_agent_run",
  "marketing_campaign",
  "image_generation",
  "project",
  "team_member",
  "code_edit",
  "seo_generation",
];

function formatLimit(value: number | null | undefined) {
  if (value === null || value === undefined) return "Unlimited";
  return value.toLocaleString();
}

export function PlanComparisonTable({ plans }: { plans: BillingPlan[] }) {
  return (
    <div style={{ overflowX: "auto", borderRadius: 18, border: "1px solid #e2e8f0", background: "#fff" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
        <thead>
          <tr style={{ background: "#f8fafc" }}>
            <th style={{ textAlign: "left", padding: 16, fontSize: 12, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>Feature</th>
            {plans.map((plan) => (
              <th key={plan.slug} style={{ textAlign: "left", padding: 16, fontSize: 13, color: "#0f172a" }}>{plan.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FEATURES.map((feature) => (
            <tr key={feature} style={{ borderTop: "1px solid #e2e8f0" }}>
              <td style={{ padding: 16, fontSize: 13, fontWeight: 700, color: "#334155", textTransform: "capitalize" }}>
                {feature.replaceAll("_", " ")}
              </td>
              {plans.map((plan) => (
                <td key={`${plan.slug}-${feature}`} style={{ padding: 16, fontSize: 13, color: "#64748b" }}>
                  {formatLimit(plan.limits_json?.[feature])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
