"use client";

import type { UsageSummary } from "@/lib/types";

export function UsageMeter({ item }: { item: UsageSummary }) {
  const ratio = item.unlimited || item.limit === null ? 0 : Math.min((item.used / Math.max(item.limit, 1)) * 100, 100);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 12 }}>
        <span style={{ color: "#cbd5e1", textTransform: "capitalize" }}>{item.feature_key.replaceAll("_", " ")}</span>
        <span style={{ color: "#fff", fontWeight: 700 }}>
          {item.used}
          {item.unlimited ? " / Unlimited" : ` / ${item.limit}`}
        </span>
      </div>
      <div style={{ width: "100%", height: 8, borderRadius: 999, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
        <div
          style={{
            width: item.unlimited ? "18%" : `${ratio}%`,
            height: "100%",
            borderRadius: 999,
            background: item.unlimited
              ? "linear-gradient(135deg,#10b981,#34d399)"
              : ratio > 85
                ? "linear-gradient(135deg,#f59e0b,#ef4444)"
                : "linear-gradient(135deg,#6366f1,#8b5cf6)",
          }}
        />
      </div>
    </div>
  );
}
