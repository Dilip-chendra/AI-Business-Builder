"use client";

import { Loader2 } from "lucide-react";

type Props = {
  label: string;
  onClick: () => Promise<void>;
  loading?: boolean;
};

export function PayPalSubscribeButton({ label, onClick, loading }: Props) {
  return (
    <button
      onClick={() => onClick().catch(console.error)}
      disabled={loading}
      style={{
        border: "none",
        borderRadius: 12,
        padding: "12px 16px",
        fontWeight: 800,
        fontSize: 14,
        cursor: loading ? "not-allowed" : "pointer",
        background: "linear-gradient(135deg,#0070ba,#003087)",
        color: "#fff",
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        justifyContent: "center",
      }}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : null}
      {label}
    </button>
  );
}
