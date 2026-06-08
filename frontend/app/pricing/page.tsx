"use client";

import { useEffect, useState } from "react";

import { PricingCard } from "@/components/billing/PricingCard";
import { PlanComparisonTable } from "@/components/billing/PlanComparisonTable";
import { api } from "@/lib/api";
import type { BillingPlan, SubscriptionSummary } from "@/lib/types";

export default function PricingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listBillingPlans(), api.getSubscription()])
      .then(([planList, current]) => {
        setPlans(planList);
        setSubscription(current);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function subscribe(planSlug: string) {
    if (planSlug === "free") return;
    setBusySlug(planSlug);
    setError(null);
    try {
      const result = await api.createPayPalSubscription(planSlug as "pro_monthly" | "pro_yearly" | "team_monthly");
      window.location.href = result.approval_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the PayPal subscription");
    } finally {
      setBusySlug(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#0f172a", margin: 0 }}>Pricing</h1>
        <p style={{ color: "#64748b", margin: "8px 0 0", maxWidth: 720 }}>
          Upgrade when you need more AI requests, browser operator runs, campaigns, and collaboration room.
          Everything here is wired to real PayPal sandbox billing from the backend.
        </p>
      </div>
      {error ? (
        <div style={{ borderRadius: 14, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 14px" }}>
          {error}
        </div>
      ) : null}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
        {plans.map((plan) => (
          <PricingCard
            key={plan.slug}
            plan={plan}
            currentPlanSlug={subscription?.plan.slug}
            busySlug={busySlug}
            onSubscribe={subscribe}
          />
        ))}
      </div>
      <PlanComparisonTable plans={plans} />
    </div>
  );
}
