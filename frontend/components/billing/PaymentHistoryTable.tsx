"use client";

import type { PaymentTransaction } from "@/lib/types";

export function PaymentHistoryTable({ rows }: { rows: PaymentTransaction[] }) {
  if (rows.length === 0) {
    return (
      <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", padding: 24, color: "#64748b" }}>
        No payment history yet. Once a subscription or one-time order completes, it will appear here.
      </div>
    );
  }
  return (
    <div style={{ overflowX: "auto", borderRadius: 18, border: "1px solid #e2e8f0", background: "#fff" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
        <thead>
          <tr style={{ background: "#f8fafc" }}>
            {["Date", "Type", "Status", "Amount", "Provider ID"].map((label) => (
              <th key={label} style={{ textAlign: "left", padding: 16, fontSize: 12, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} style={{ borderTop: "1px solid #e2e8f0" }}>
              <td style={{ padding: 16, fontSize: 13, color: "#334155" }}>{new Date(row.created_at).toLocaleString()}</td>
              <td style={{ padding: 16, fontSize: 13, color: "#334155", textTransform: "capitalize" }}>{row.type.replaceAll("_", " ")}</td>
              <td style={{ padding: 16, fontSize: 13, color: "#334155", textTransform: "capitalize" }}>{row.status.replaceAll("_", " ")}</td>
              <td style={{ padding: 16, fontSize: 13, color: "#0f172a", fontWeight: 700 }}>
                {row.currency} {(row.amount_cents / 100).toFixed(2)}
              </td>
              <td style={{ padding: 16, fontSize: 12, color: "#64748b" }}>{row.provider_payment_id || row.provider_order_id || row.provider_subscription_id || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
