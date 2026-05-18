"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, CreditCard, Crown, RefreshCw, ShieldCheck, Sparkles, Wallet } from "lucide-react";

import { PaymentHistoryTable } from "@/components/billing/PaymentHistoryTable";
import { api } from "@/lib/api";
import type { BillingPlan, PaymentTransaction, SubscriptionSummary, UsageSummary } from "@/lib/types";

type PayPalSubscriptionSlug = "pro_monthly" | "pro_yearly" | "team_monthly";

function formatMoney(cents: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

function formatInterval(plan: BillingPlan) {
  if (plan.interval === "free") return "Free forever";
  if (plan.interval === "month") return "per month";
  if (plan.interval === "year") return "per year";
  return plan.interval;
}

function featureLabel(featureKey: string) {
  return featureKey
    .replaceAll("_", " ")
    .replace(/\bai\b/gi, "AI")
    .replace(/\bseo\b/gi, "SEO")
    .replace(/\bcode\b/gi, "Code")
    .replace(/\bbrowser\b/gi, "Browser")
    .replace(/\bmarketing\b/gi, "Marketing")
    .replace(/\bproject\b/gi, "Project")
    .replace(/\bteam\b/gi, "Team")
    .replace(/\bmember\b/gi, "Member")
    .replace(/\brequest\b/gi, "Request")
    .replace(/\brun\b/gi, "Run")
    .replace(/\bgeneration\b/gi, "Generation")
    .replace(/\bedit\b/gi, "Edit")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function usagePercent(item: UsageSummary) {
  if (item.unlimited || !item.limit || item.limit <= 0) return 0;
  return Math.min(100, Math.round((item.used / item.limit) * 100));
}

function planAccent(slug: string) {
  if (slug.includes("team")) {
    return {
      gradient: "linear-gradient(135deg,#0f172a,#1e293b 52%,#334155)",
      glow: "rgba(15,23,42,0.35)",
      chip: "#c7d2fe",
    };
  }
  if (slug.includes("pro")) {
    return {
      gradient: "linear-gradient(135deg,#312e81,#4f46e5 52%,#7c3aed)",
      glow: "rgba(99,102,241,0.35)",
      chip: "#ddd6fe",
    };
  }
  return {
    gradient: "linear-gradient(135deg,#0f172a,#111827 52%,#1f2937)",
    glow: "rgba(15,23,42,0.22)",
    chip: "#d1fae5",
  };
}

function UsageCard({ item }: { item: UsageSummary }) {
  const percent = usagePercent(item);
  const exhausted = !item.unlimited && item.remaining !== null && item.remaining <= 0;
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 18, padding: 18, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <p style={{ margin: 0, fontSize: 12, color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            {featureLabel(item.feature_key)}
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 26, color: "#0f172a", fontWeight: 900 }}>
            {item.unlimited ? "∞" : item.used}
            <span style={{ fontSize: 14, color: "#94a3b8", fontWeight: 700, marginLeft: 6 }}>
              {item.unlimited ? "Unlimited" : `/ ${item.limit}`}
            </span>
          </p>
        </div>
        <div style={{
          minWidth: 72,
          textAlign: "right",
          color: exhausted ? "#dc2626" : "#16a34a",
          fontWeight: 800,
          fontSize: 13,
        }}>
          {item.unlimited ? "Always on" : `${item.remaining ?? 0} left`}
        </div>
      </div>
      {!item.unlimited ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ height: 10, borderRadius: 999, background: "#e2e8f0", overflow: "hidden" }}>
            <div
              style={{
                width: `${percent}%`,
                height: "100%",
                borderRadius: 999,
                background: exhausted
                  ? "linear-gradient(90deg,#f97316,#dc2626)"
                  : "linear-gradient(90deg,#6366f1,#8b5cf6)",
              }}
            />
          </div>
          <p style={{ margin: 0, fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
            {exhausted
              ? "This feature has reached its current limit. Upgrade to unlock more room."
              : "Usage updates in real time as you run AI, browser, and marketing actions."}
          </p>
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
          This feature is available without a hard ceiling on the current plan.
        </p>
      )}
    </div>
  );
}

export default function BillingPage() {
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [transactions, setTransactions] = useState<PaymentTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [upgradingSlug, setUpgradingSlug] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sub, tx, availablePlans] = await Promise.all([
        api.getSubscription(),
        api.listPaymentTransactions(),
        api.listBillingPlans(),
      ]);
      setSubscription(sub);
      setTransactions(tx);
      setPlans(availablePlans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load billing data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch(console.error);
  }, []);

  async function cancelSubscription() {
    setCancelling(true);
    setError(null);
    try {
      await api.cancelPayPalSubscription();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel the subscription");
    } finally {
      setCancelling(false);
    }
  }

  async function startPlan(planSlug: PayPalSubscriptionSlug) {
    setUpgradingSlug(planSlug);
    setError(null);
    try {
      const result = await api.createPayPalSubscription(planSlug);
      window.location.href = result.approval_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start subscription");
    } finally {
      setUpgradingSlug(null);
    }
  }

  const currentPlan = subscription?.plan ?? null;
  const currentAccent = currentPlan ? planAccent(currentPlan.slug) : planAccent("free");

  const topUsage = useMemo(() => (subscription?.usage ?? []).slice(0, 6), [subscription]);
  const nextPaidPlans = useMemo(
    () => plans.filter((plan) => plan.slug !== currentPlan?.slug).sort((a, b) => a.price_cents - b.price_cents),
    [plans, currentPlan?.slug],
  );
  const totalRevenue = useMemo(
    () => transactions.filter((row) => row.status === "completed" || row.status === "active").reduce((sum, row) => sum + row.amount_cents, 0),
    [transactions],
  );

  if (loading) {
    return (
      <div style={{ display: "grid", gap: 18 }}>
        <div style={{ height: 220, borderRadius: 24, background: "linear-gradient(135deg,#e2e8f0,#f8fafc)", border: "1px solid #e2e8f0" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} style={{ height: 140, borderRadius: 18, background: "#f8fafc", border: "1px solid #e2e8f0" }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ fontSize: 30, fontWeight: 900, color: "#0f172a", margin: 0 }}>Billing & Plans</h1>
          <p style={{ color: "#64748b", margin: "8px 0 0", maxWidth: 760, lineHeight: 1.6 }}>
            Run the operating system on a real billing foundation: plan controls, usage visibility, payment history, and secure PayPal-backed subscriptions.
          </p>
        </div>
        <button
          onClick={() => load().catch(console.error)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            borderRadius: 14,
            border: "1px solid #dbe4f0",
            background: "#fff",
            color: "#334155",
            padding: "12px 16px",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 12px 30px rgba(15,23,42,0.05)",
          }}
        >
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>

      {error ? (
        <div style={{ borderRadius: 16, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "14px 16px", fontWeight: 600 }}>
          {error}
        </div>
      ) : null}

      {subscription && currentPlan ? (
        <section
          style={{
            position: "relative",
            overflow: "hidden",
            borderRadius: 26,
            padding: 28,
            background: currentAccent.gradient,
            color: "#fff",
            boxShadow: `0 24px 60px ${currentAccent.glow}`,
            display: "grid",
            gap: 24,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
            <div style={{ maxWidth: 640 }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, borderRadius: 999, background: "rgba(255,255,255,0.14)", padding: "8px 12px", fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: currentAccent.chip }}>
                <Crown size={14} />
                Current Plan
              </div>
              <h2 style={{ margin: "14px 0 8px", fontSize: 34, fontWeight: 900, letterSpacing: "-0.03em" }}>{currentPlan.name}</h2>
              <p style={{ margin: 0, color: "rgba(255,255,255,0.72)", fontSize: 15, lineHeight: 1.7, maxWidth: 620 }}>
                {currentPlan.description}
              </p>
            </div>

            <div style={{ display: "grid", gap: 12, minWidth: 280 }}>
              <div style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.18)", borderRadius: 18, padding: 18 }}>
                <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.58)", fontWeight: 800 }}>Plan Value</div>
                <div style={{ marginTop: 8, display: "flex", alignItems: "baseline", gap: 8 }}>
                  <span style={{ fontSize: 34, fontWeight: 900 }}>{currentPlan.price_cents === 0 ? "Free" : formatMoney(currentPlan.price_cents, currentPlan.currency)}</span>
                  <span style={{ color: "rgba(255,255,255,0.68)", fontWeight: 700 }}>{formatInterval(currentPlan)}</span>
                </div>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {currentPlan.slug !== "team_monthly" ? (
                  <button
                    onClick={() => startPlan(currentPlan.slug === "free" ? "pro_monthly" : "team_monthly").catch(console.error)}
                    disabled={!!upgradingSlug}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      borderRadius: 14,
                      border: "none",
                      background: "#fff",
                      color: "#1e1b4b",
                      padding: "13px 18px",
                      fontWeight: 800,
                      cursor: upgradingSlug ? "not-allowed" : "pointer",
                      minWidth: 170,
                    }}
                  >
                    {upgradingSlug ? "Redirecting..." : "Upgrade Plan"}
                    <ArrowRight size={15} />
                  </button>
                ) : null}
                {subscription.provider_subscription_id && subscription.status !== "cancelled" ? (
                  <button
                    onClick={() => cancelSubscription().catch(console.error)}
                    disabled={cancelling}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      borderRadius: 14,
                      border: "1px solid rgba(255,255,255,0.22)",
                      background: "rgba(255,255,255,0.08)",
                      color: "#fff",
                      padding: "13px 18px",
                      fontWeight: 800,
                      cursor: cancelling ? "not-allowed" : "pointer",
                    }}
                  >
                    {cancelling ? "Cancelling..." : "Cancel Subscription"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
            {[
              {
                icon: ShieldCheck,
                title: "Status",
                value: subscription.status.replaceAll("_", " "),
                detail: subscription.provider_subscription_id ? "PayPal subscription linked" : "Free access active",
              },
              {
                icon: RefreshCw,
                title: "Renewal",
                value: subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : "Not scheduled",
                detail: subscription.current_period_end ? "Current billing window end" : "No renewal date for this plan",
              },
              {
                icon: Wallet,
                title: "Revenue Logged",
                value: formatMoney(totalRevenue, currentPlan.currency),
                detail: transactions.length ? `${transactions.length} transaction${transactions.length === 1 ? "" : "s"} tracked` : "No completed payments yet",
              },
              {
                icon: Sparkles,
                title: "Plan Coverage",
                value: `${subscription.usage.filter((item) => item.unlimited || (item.remaining ?? 0) > 0).length}/${subscription.usage.length}`,
                detail: "Tracked limits still available",
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} style={{ borderRadius: 18, background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.14)", padding: 18 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, color: "rgba(255,255,255,0.72)" }}>
                    <Icon size={15} />
                    <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 800 }}>{item.title}</span>
                  </div>
                  <div style={{ marginTop: 12, fontSize: 24, fontWeight: 900, textTransform: "capitalize" }}>{item.value}</div>
                  <p style={{ margin: "8px 0 0", fontSize: 13, color: "rgba(255,255,255,0.62)", lineHeight: 1.6 }}>{item.detail}</p>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {topUsage.length > 0 ? (
        <section style={{ display: "grid", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 20, color: "#0f172a", fontWeight: 900 }}>Usage Overview</h2>
              <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 14 }}>
                Watch the features that matter most as you build, market, and operate your business.
              </p>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {topUsage.map((item) => <UsageCard key={item.feature_key} item={item} />)}
          </div>
        </section>
      ) : null}

      {nextPaidPlans.length > 0 ? (
        <section style={{ display: "grid", gap: 14 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, color: "#0f172a", fontWeight: 900 }}>Upgrade Paths</h2>
            <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 14 }}>
              Move up only when you need more capacity. The plans below are live PayPal-backed upgrade options.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 16 }}>
            {nextPaidPlans.map((plan) => {
              const accent = planAccent(plan.slug);
              const standoutFeatures = Object.entries(plan.limits_json)
                .slice(0, 4)
                .map(([key, value]) => `${featureLabel(key)}: ${value === null ? "Unlimited" : value}`);

              return (
                <div
                  key={plan.id}
                  style={{
                    borderRadius: 22,
                    overflow: "hidden",
                    border: "1px solid #e2e8f0",
                    background: "#fff",
                    boxShadow: "0 18px 40px rgba(15,23,42,0.06)",
                    display: "grid",
                  }}
                >
                  <div style={{ padding: 22, background: accent.gradient, color: "#fff" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                      <div style={{ fontSize: 18, fontWeight: 900 }}>{plan.name}</div>
                      {plan.slug === currentPlan?.slug ? (
                        <span style={{ background: "rgba(255,255,255,0.18)", borderRadius: 999, padding: "6px 10px", fontSize: 11, fontWeight: 800 }}>
                          Current
                        </span>
                      ) : null}
                    </div>
                    <div style={{ marginTop: 14, display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontSize: 34, fontWeight: 900 }}>
                        {plan.price_cents === 0 ? "Free" : formatMoney(plan.price_cents, plan.currency)}
                      </span>
                      <span style={{ color: "rgba(255,255,255,0.72)", fontWeight: 700 }}>{formatInterval(plan)}</span>
                    </div>
                    <p style={{ margin: "10px 0 0", color: "rgba(255,255,255,0.72)", lineHeight: 1.6, fontSize: 14 }}>
                      {plan.description}
                    </p>
                  </div>

                  <div style={{ padding: 22, display: "grid", gap: 16 }}>
                    <div style={{ display: "grid", gap: 10 }}>
                      {standoutFeatures.map((feature) => (
                        <div key={feature} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#334155" }}>
                          <CheckCircle2 size={14} color="#16a34a" />
                          <span>{feature}</span>
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={() => startPlan(plan.slug as PayPalSubscriptionSlug).catch(console.error)}
                      disabled={!!upgradingSlug || plan.slug === currentPlan?.slug || plan.interval === "free"}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 8,
                        borderRadius: 14,
                        border: "none",
                        background: plan.slug === currentPlan?.slug ? "#e2e8f0" : "#0f172a",
                        color: plan.slug === currentPlan?.slug ? "#64748b" : "#fff",
                        padding: "13px 16px",
                        fontWeight: 800,
                        cursor: (!!upgradingSlug || plan.slug === currentPlan?.slug || plan.interval === "free") ? "not-allowed" : "pointer",
                        opacity: (!!upgradingSlug || plan.slug === currentPlan?.slug || plan.interval === "free") ? 0.75 : 1,
                      }}
                    >
                      {plan.slug === currentPlan?.slug
                        ? "Already Active"
                        : upgradingSlug === plan.slug
                          ? "Redirecting..."
                          : plan.interval === "free"
                            ? "Included"
                            : "Choose Plan"}
                      {plan.slug !== currentPlan?.slug && plan.interval !== "free" ? <ArrowRight size={15} /> : null}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      <section style={{ display: "grid", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 38, height: 38, borderRadius: 12, background: "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <CreditCard size={18} color="#4f46e5" />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, color: "#0f172a", fontWeight: 900 }}>Payment History</h2>
            <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 14 }}>
              Every completed one-time order and subscription payment shows up here with its provider references.
            </p>
          </div>
        </div>
        <PaymentHistoryTable rows={transactions} />
      </section>
    </div>
  );
}
