import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";

// Lazy load the heavy Ops client component
const OpsClient = dynamic(() => import("./OpsClient"), {
  ssr: false,
  loading: () => (
    <div style={{ padding: 40, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
      <Loader2 size={32} color="#6366f1" className="animate-spin" />
      <span style={{ color: "#64748b", fontSize: 14, fontWeight: 600 }}>Loading Ops Telemetry...</span>
      <style>{`.animate-spin { animation: spin 1s linear infinite; } @keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  ),
});

export default function OpsPage() {
  return <OpsClient />;
}
