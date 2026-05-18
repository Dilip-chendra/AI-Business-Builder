"use client";

import type { CSSProperties } from "react";
import { Link, Loader2, Settings } from "lucide-react";

type IntegrationSetupState = {
  provider: string;
  providerLabel: string;
  redirectUri?: string;
  scopes?: string[];
  requiredEnvVars?: string[];
  message: string;
  connectMode: string;
  clientId: string;
  clientSecret: string;
  clientIdConfigured?: boolean;
  clientSecretConfigured?: boolean;
  clientIdPreview?: string | null;
  readyToConnect?: boolean;
};

type Props = {
  setup: IntegrationSetupState | null;
  saving: boolean;
  onClose: () => void;
  onChange: (next: IntegrationSetupState) => void;
  onSave: (testAfterSave: boolean) => void;
};

const inputStyle: CSSProperties = {
  width: "100%",
  borderRadius: 12,
  border: "1px solid #dbe2ea",
  padding: "11px 12px",
  fontSize: 14,
  outline: "none",
  color: "#0f172a",
  background: "#fff",
  fontFamily: "inherit",
};

const btnSecondary: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  borderRadius: 10,
  border: "1px solid #dbe2ea",
  background: "#fff",
  color: "#334155",
  padding: "10px 14px",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  fontFamily: "inherit",
};

const btnPrimary: CSSProperties = {
  ...btnSecondary,
  border: "none",
  background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
  color: "#fff",
  boxShadow: "0 12px 30px rgba(99,102,241,0.25)",
};

export function IntegrationSetupModal({ setup, saving, onClose, onChange, onSave }: Props) {
  if (!setup) return null;

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 97 }}
      />
      <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(720px, calc(100vw - 32px))", maxHeight: "calc(100vh - 48px)", overflowY: "auto", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 98, padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Integration Setup</p>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>{setup.providerLabel}</h3>
          </div>
          <button onClick={onClose} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
        </div>
        <div style={{ display: "grid", gap: 14 }}>
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
            <p style={{ fontSize: 13, color: "#334155", margin: 0, lineHeight: 1.7 }}>{setup.message}</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Mode</p>
              <p style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", margin: 0 }}>
                {setup.connectMode === "oauth" ? "Official OAuth" : "Browser Automation / API Key"}
              </p>
            </div>
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Current Status</p>
              <p style={{ fontSize: 13, fontWeight: 700, color: setup.readyToConnect ? "#16a34a" : "#d97706", margin: 0 }}>
                {setup.readyToConnect ? "Ready to connect" : "Needs credentials"}
              </p>
              {setup.clientIdPreview && (
                <p style={{ fontSize: 12, color: "#64748b", margin: "6px 0 0" }}>
                  Saved client ID: <code>{setup.clientIdPreview}</code>
                </p>
              )}
            </div>
          </div>
          {setup.redirectUri && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Redirect URI</p>
              <code style={{ display: "block", fontSize: 12, color: "#1d4ed8", wordBreak: "break-all" }}>{setup.redirectUri}</code>
              <p style={{ fontSize: 12, color: "#64748b", margin: "10px 0 0", lineHeight: 1.6 }}>
                Register this exact callback URL in the provider portal. We keep business and user context in secure OAuth state, not in the redirect URI.
              </p>
            </div>
          )}
          {setup.connectMode === "oauth" && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16, display: "grid", gap: 12 }}>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6, display: "block", textTransform: "uppercase", letterSpacing: "0.08em" }}>Client ID</label>
                <input
                  value={setup.clientId}
                  onChange={(e) => onChange({ ...setup, clientId: e.target.value })}
                  placeholder={setup.clientIdConfigured ? "Saved. Paste a new client ID to replace it." : "Enter provider client ID"}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6, display: "block", textTransform: "uppercase", letterSpacing: "0.08em" }}>Client Secret</label>
                <input
                  type="password"
                  value={setup.clientSecret}
                  onChange={(e) => onChange({ ...setup, clientSecret: e.target.value })}
                  placeholder={setup.clientSecretConfigured ? "Saved. Paste a new secret to replace it." : "Enter provider client secret"}
                  style={inputStyle}
                />
              </div>
              <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>
                These credentials are saved locally to <code>backend/.env</code> for development and loaded into the running backend immediately.
              </p>
            </div>
          )}
          {setup.requiredEnvVars && setup.requiredEnvVars.length > 0 && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Environment Variables Needed</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {setup.requiredEnvVars.map((name) => (
                  <span key={name} style={{ background: "#eef2ff", color: "#4f46e5", borderRadius: 999, padding: "5px 10px", fontSize: 12, fontWeight: 700 }}>{name}</span>
                ))}
              </div>
            </div>
          )}
          {setup.scopes && setup.scopes.length > 0 && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Requested Scopes</p>
              <ul style={{ margin: 0, paddingLeft: 18, color: "#334155", fontSize: 13, lineHeight: 1.7 }}>
                {setup.scopes.map((scope) => <li key={scope}>{scope}</li>)}
              </ul>
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, flexWrap: "wrap" }}>
            {setup.connectMode === "oauth" && (
              <>
                <button onClick={() => onSave(false)} disabled={saving} style={btnSecondary}>
                  {saving ? <Loader2 size={13} /> : <Settings size={13} />} Save settings
                </button>
                <button onClick={() => onSave(true)} disabled={saving} style={btnPrimary}>
                  {saving ? <Loader2 size={13} /> : <Link size={13} />} Save and test connection
                </button>
              </>
            )}
            <button onClick={onClose} style={btnSecondary}>Close</button>
          </div>
        </div>
      </div>
    </>
  );
}
