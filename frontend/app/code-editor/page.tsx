import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";

// Lazy load the heavy code editor client component
const CodeEditorClient = dynamic(() => import("./CodeEditorClient"), {
  ssr: false,
  loading: () => (
    <div style={{ height: "calc(100vh - 120px)", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a", borderRadius: 20, border: "1px solid rgba(255,255,255,0.08)" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
        <Loader2 size={32} color="#6366f1" className="animate-spin" />
        <span style={{ color: "#94a3b8", fontSize: 14, fontWeight: 600 }}>Loading Editor Environment...</span>
      </div>
      <style>{`.animate-spin { animation: spin 1s linear infinite; } @keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  ),
});

export default function CodeEditorPage() {
  return <CodeEditorClient />;
}
