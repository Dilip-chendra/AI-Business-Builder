"use client";

import type { SubscriptionSummary } from "@/lib/types";
import { UsageMeter } from "./UsageMeter";

export function BillingStatusCard({ subscription }: { subscription: SubscriptionSummary }) {
  return (
    <div style={{ background: "#0f172a", borderRadius: 20, padding: 24, color: "#fff", display: "grid", gap: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.45)" }}>Current Plan</div>
          <h2 style={{ fontSize: 26, fontWeight: 900, margin: "8px 0 0" }}>{subscription.plan.name}</h2>
          <p style={{ margin: "8px 0 0", color: "rgba(255,255,255,0.6)" }}>{subscription.plan.description}</p>
        </div>
        <div style={{ minWidth: 220 }}>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 8 }}>Status</div>
          <div style={{ fontWeight: 800, fontSize: 15, textTransform: "capitalize" }}>{subscription.status.replaceAll("_", " ")}</div>
          {subscription.current_period_end ? (
            <div style={{ marginTop: 8, fontSize: 13, color: "rgba(255,255,255,0.65)" }}>
              Renews: {new Date(subscription.current_period_end).toLocaleString()}
            </div>
          ) : null}
        </div>
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        {subscription.usage.map((item) => <UsageMeter key={item.feature_key} item={item} />)}
      </div>
    </div>
  );
}
