"use client";

import { RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  console.error("Global application failure", error);

  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#0f172a", color: "#f8fafc", fontFamily: "Inter, Segoe UI, sans-serif" }}>
        <main
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
          }}
        >
          <section
            style={{
              width: "min(620px, 100%)",
              border: "1px solid #243041",
              borderRadius: 18,
              background: "#111827",
              padding: 24,
              boxShadow: "0 24px 80px rgba(0,0,0,0.35)",
            }}
          >
            <p style={{ margin: "0 0 8px", color: "#fbbf24", fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Application recovery
            </p>
            <h1 style={{ margin: "0 0 10px", fontSize: 26, fontWeight: 850 }}>
              AI Business Builder hit a startup error
            </h1>
            <p style={{ margin: "0 0 18px", color: "#94a3b8", fontSize: 14, lineHeight: 1.7 }}>
              The frontend shell failed before the page could mount. Retry the app after the local server finishes rebuilding.
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
              Retry app
            </button>
          </section>
        </main>
      </body>
    </html>
  );
}
