"use client";

import Link from "next/link";

export default function BillingCancelPage() {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto", display: "grid", gap: 20 }}>
      <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: 32 }}>
        <h1 style={{ margin: 0, fontSize: 30, fontWeight: 900, color: "#0f172a" }}>Billing Not Completed</h1>
        <p style={{ margin: "12px 0 0", color: "#64748b", lineHeight: 1.7 }}>
          The PayPal approval flow was cancelled or interrupted. Nothing was upgraded silently. You can retry from pricing whenever you're ready.
        </p>
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <Link href="/pricing" style={{ textDecoration: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 800, borderRadius: 12, padding: "12px 16px" }}>
          Retry Upgrade
        </Link>
        <Link href="/billing" style={{ textDecoration: "none", background: "#fff", color: "#334155", fontWeight: 700, borderRadius: 12, padding: "12px 16px", border: "1px solid #e2e8f0" }}>
          Open Billing
        </Link>
      </div>
    </div>
  );
}
