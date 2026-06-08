"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect } from "react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route rendering failed", error);
  }, [error]);

  return (
    <main
      style={{
        minHeight: "calc(100vh - 80px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background: "#0f172a",
      }}
    >
      <section
        style={{
          width: "min(620px, 100%)",
          border: "1px solid #243041",
          borderRadius: 18,
          background: "linear-gradient(180deg,#111827,#0b1120)",
          padding: 24,
          boxShadow: "0 24px 80px rgba(0,0,0,0.28)",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 14,
            background: "rgba(251,191,36,0.12)",
            color: "#fbbf24",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 16,
          }}
        >
          <AlertTriangle size={22} />
        </div>
        <h1 style={{ color: "#f8fafc", fontSize: 24, margin: "0 0 8px", fontWeight: 800 }}>
          This page hit a recoverable error
        </h1>
        <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.7, margin: "0 0 18px" }}>
          The app is still running. Retry this route, or use the sidebar to open another workspace page while the issue is logged in the browser console.
        </p>
        {error?.message && (
          <pre
            style={{
              whiteSpace: "pre-wrap",
              color: "#cbd5e1",
              background: "#020617",
              border: "1px solid #1e293b",
              borderRadius: 12,
              padding: 12,
              fontSize: 12,
              lineHeight: 1.5,
              maxHeight: 180,
              overflow: "auto",
            }}
          >
            {error.message}
          </pre>
        )}
        <button
          onClick={reset}
          style={{
            marginTop: 18,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            border: "none",
            borderRadius: 12,
            padding: "11px 15px",
            background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
            color: "#fff",
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          <RefreshCw size={15} />
          Retry page
        </button>
      </section>
    </main>
  );
}
