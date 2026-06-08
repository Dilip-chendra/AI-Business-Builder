"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import type { SubscriptionSummary } from "@/lib/types";

export default function BillingSuccessPage() {
  const search = useSearchParams();
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSubscription()
      .then(setSubscription)
      .catch((err: Error) => setError(err.message));
  }, [search]);

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", display: "grid", gap: 20 }}>
      <div style={{ background: "#0f172a", color: "#fff", borderRadius: 24, padding: 32 }}>
        <h1 style={{ margin: 0, fontSize: 32, fontWeight: 900 }}>Billing Success</h1>
        <p style={{ margin: "12px 0 0", color: "rgba(255,255,255,0.65)", lineHeight: 1.7 }}>
          PayPal sent you back successfully. We're refreshing the real subscription state from the backend now.
        </p>
      </div>
      {error ? <div style={{ color: "#b91c1c" }}>{error}</div> : null}
      {subscription ? (
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 24 }}>
          <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "#64748b" }}>Current status</div>
          <h2 style={{ margin: "8px 0 0", fontSize: 22, fontWeight: 900 }}>{subscription.plan.name}</h2>
          <p style={{ color: "#334155", margin: "10px 0 0" }}>
            Status: <strong>{subscription.status}</strong>
          </p>
        </div>
      ) : null}
      <div style={{ display: "flex", gap: 12 }}>
        <Link href="/billing" style={{ textDecoration: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 800, borderRadius: 12, padding: "12px 16px" }}>
          Open Billing
        </Link>
        <Link href="/dashboard" style={{ textDecoration: "none", background: "#fff", color: "#334155", fontWeight: 700, borderRadius: 12, padding: "12px 16px", border: "1px solid #e2e8f0" }}>
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
