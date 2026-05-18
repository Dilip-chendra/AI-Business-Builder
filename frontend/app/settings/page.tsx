"use client";

import { useEffect, useState } from "react";
import { CheckCircle, Loader2, ExternalLink, Settings, User, CreditCard, Cpu, Globe } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";

const TABS = [
  { id: "profile",      label: "Profile",      icon: User },
  { id: "integrations", label: "Integrations", icon: CreditCard },
  { id: "ai",           label: "AI Providers", icon: Cpu },
  { id: "env",          label: "Environment",  icon: Globe },
];

export default function SettingsPage() {
  const { user, isLoading: authLoading } = useAuth();
  const [tab, setTab] = useState("profile");
  const [form, setForm] = useState({ full_name: "", stripe_publishable_key: "", groq_api_key: "", hf_api_key: "", openai_api_key: "", sendgrid_api_key: "" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) setForm((f) => ({ ...f, full_name: user.full_name || "", stripe_publishable_key: (user as any).stripe_publishable_key || "" }));
    api.getApiKeys().then(keys => setForm((f) => ({ ...f, ...keys }))).catch(() => {});
  }, [user]);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(""); setSaved(false);
    try { await api.updateSettings(form); setSaved(true); setTimeout(() => setSaved(false), 3000); }
    catch (err: any) { setError(err.message || "Failed to update settings."); }
    finally { setSaving(false); }
  }

  if (authLoading) return <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}><Loader2 size={28} className="animate-spin" style={{ color: "#cbd5e1" }} /></div>;

  const initial = (user?.full_name || user?.email || "U")[0].toUpperCase();

  return (
    <div className="anim-fade-in" style={{ maxWidth: 680, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Settings size={24} style={{ color: "#6366f1" }} /> Settings
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Manage your profile and integration keys.</p>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, background: "#f1f5f9", borderRadius: 14, padding: 4 }}>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              borderRadius: 10, padding: "8px 12px", fontSize: 13, fontWeight: 600,
              border: "none", cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
              background: tab === id ? "#fff" : "transparent",
              color: tab === id ? "#0f172a" : "#94a3b8",
              boxShadow: tab === id ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
            }}
          >
            <Icon size={14} /> <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {error && <div style={{ borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>{error}</div>}

      {/* Profile */}
      {tab === "profile" && (
        <form onSubmit={save} style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "28px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>Profile Information</h2>

          {/* Avatar */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, background: "#f8fafc", borderRadius: 14, border: "1px solid #e2e8f0", padding: "16px 18px" }}>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 900, fontSize: 20, boxShadow: "0 4px 16px rgba(99,102,241,0.35)", flexShrink: 0 }}>
              {initial}
            </div>
            <div>
              <p style={{ fontWeight: 800, fontSize: 15, color: "#0f172a", margin: "0 0 2px" }}>{user?.full_name || "No name set"}</p>
              <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>{user?.email}</p>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>Display name</label>
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Your name"
              style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "10px 12px", fontSize: 14, color: "#0f172a", outline: "none", fontFamily: "inherit", transition: "border-color 0.15s" }}
              onFocus={(e) => { e.target.style.borderColor = "#6366f1"; e.target.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; }}
              onBlur={(e) => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>Email address</label>
            <div style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f1f5f9", padding: "10px 12px", fontSize: 14, color: "#94a3b8" }}>{user?.email}</div>
            <p style={{ fontSize: 11, color: "#94a3b8", margin: 0 }}>Email cannot be changed after signup.</p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button type="submit" disabled={saving} className="btn-glow"
              style={{ display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700, fontSize: 14, padding: "11px 22px", borderRadius: 12, border: "none", cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}>
              {saving && <Loader2 size={15} className="animate-spin" />}
              {saving ? "Saving..." : "Save Changes"}
            </button>
            {saved && <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "#10b981" }}><CheckCircle size={15} /> Saved!</span>}
          </div>
        </form>
      )}

      {/* Integrations */}
      {tab === "integrations" && (
        <form onSubmit={save} style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "28px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 20 }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>Stripe Integration</h2>
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
              Your publishable key is used for client-side checkout. The secret key is set via{" "}
              <code style={{ background: "#f1f5f9", padding: "1px 6px", borderRadius: 4, fontSize: 12 }}>STRIPE_SECRET_KEY</code> in the backend.
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>Publishable key</label>
            <input value={form.stripe_publishable_key} onChange={(e) => setForm({ ...form, stripe_publishable_key: e.target.value })} placeholder="pk_live_..."
              style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "10px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "monospace", transition: "border-color 0.15s" }}
              onFocus={(e) => { e.target.style.borderColor = "#6366f1"; e.target.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; }}
              onBlur={(e) => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
            />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button type="submit" disabled={saving} className="btn-glow"
              style={{ display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700, fontSize: 14, padding: "11px 22px", borderRadius: 12, border: "none", cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}>
              {saving && <Loader2 size={15} className="animate-spin" />}
              {saving ? "Saving..." : "Save Changes"}
            </button>
            {saved && <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "#10b981" }}><CheckCircle size={15} /> Saved!</span>}
          </div>
        </form>
      )}

      {/* AI Providers */}
      {tab === "ai" && (
        <form onSubmit={async (e) => {
          e.preventDefault();
          setSaving(true); setError(""); setSaved(false);
          try {
            await api.updateApiKeys({
              groq_api_key: form.groq_api_key,
              hf_api_key: form.hf_api_key,
              openai_api_key: form.openai_api_key,
              sendgrid_api_key: form.sendgrid_api_key
            });
            setSaved(true); setTimeout(() => setSaved(false), 3000);
          } catch (err: any) { setError(err.message || "Failed to save API keys."); }
          finally { setSaving(false); }
        }} style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "28px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 6px" }}>AI & Integration Keys</h2>
              <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>These keys are securely encrypted in the database.</p>
            </div>
            <a href="/ai-status" style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, fontWeight: 600, color: "#6366f1", textDecoration: "none", whiteSpace: "nowrap" }}>
              View status <ExternalLink size={13} />
            </a>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[
              { id: "groq", label: "Groq API Key", key: "groq_api_key", placeholder: "gsk_..." },
              { id: "hf", label: "HuggingFace Token", key: "hf_api_key", placeholder: "hf_..." },
              { id: "openai", label: "OpenAI API Key", key: "openai_api_key", placeholder: "sk-..." },
              { id: "sendgrid", label: "SendGrid API Key", key: "sendgrid_api_key", placeholder: "SG...." },
            ].map(({ id, label, key, placeholder }) => (
              <div key={id} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>{label}</label>
                <input 
                  value={(form as any)[key] || ""} 
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })} 
                  placeholder={placeholder}
                  type="password"
                  style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "10px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "monospace", transition: "border-color 0.15s" }}
                  onFocus={(e) => { e.target.style.borderColor = "#6366f1"; e.target.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; }}
                  onBlur={(e) => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button type="submit" disabled={saving} className="btn-glow"
              style={{ display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700, fontSize: 14, padding: "11px 22px", borderRadius: 12, border: "none", cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}>
              {saving && <Loader2 size={15} className="animate-spin" />}
              {saving ? "Saving..." : "Save API Keys"}
            </button>
            {saved && <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "#10b981" }}><CheckCircle size={15} /> Saved!</span>}
          </div>
        </form>
      )}

      {/* Environment */}
      {tab === "env" && (
        <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "28px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", gap: 16 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>Environment</h2>
          {[
            { label: "API URL", value: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1" },
            { label: "Environment", value: process.env.NODE_ENV || "development" },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#f8fafc", borderRadius: 12, border: "1px solid #e2e8f0", padding: "12px 16px" }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>{label}</span>
              <code style={{ fontSize: 12, background: "#e2e8f0", padding: "3px 8px", borderRadius: 6, color: "#0f172a" }}>{value}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
