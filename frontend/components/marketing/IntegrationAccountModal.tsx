"use client";

import type { CSSProperties } from "react";
import { KeyRound, Loader2, ShieldCheck, Trash2 } from "lucide-react";

export type IntegrationAccountModalState = {
  platform: string;
  label: string;
  email: string;
  phone: string;
  password: string;
  status: string;
  identifierPreview: string;
  lastTestedAt?: string | null;
  lastError?: string | null;
};

type Props = {
  account: IntegrationAccountModalState | null;
  saving: boolean;
  testing: boolean;
  deleting: boolean;
  onClose: () => void;
  onChange: (next: IntegrationAccountModalState) => void;
  onSave: () => void;
  onTest: () => void;
  onDelete: () => void;
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

const btnDanger: CSSProperties = {
  ...btnSecondary,
  border: "1px solid #fecaca",
  background: "#fff1f2",
  color: "#dc2626",
};

export function IntegrationAccountModal({
  account,
  saving,
  testing,
  deleting,
  onClose,
  onChange,
  onSave,
  onTest,
  onDelete,
}: Props) {
  if (!account) return null;

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 97 }} />
      <div style={{ position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)", width: "min(680px, calc(100vw - 32px))", maxHeight: "calc(100vh - 48px)", overflowY: "auto", background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", boxShadow: "0 24px 80px rgba(15,23,42,0.25)", zIndex: 98, padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.08em" }}>Browser Account Vault</p>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0 }}>{account.label}</h3>
          </div>
          <button onClick={onClose} style={{ background: "#f1f5f9", border: "none", borderRadius: 10, width: 34, height: 34, cursor: "pointer", color: "#64748b", fontSize: 16 }}>x</button>
        </div>

        <div style={{ display: "grid", gap: 14 }}>
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 14, padding: 16, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <div>
                <p style={{ fontSize: 13, color: "#334155", margin: 0, lineHeight: 1.7 }}>
                  Save the login details this browser operator should use when it needs to restore a platform session for publishing or verification.
                </p>
              </div>
              <span style={{ background: account.status === "connected" ? "#dcfce7" : account.status === "error" ? "#fee2e2" : "#eef2ff", color: account.status === "connected" ? "#16a34a" : account.status === "error" ? "#dc2626" : "#4f46e5", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 999 }}>
                {account.status.replace(/_/g, " ")}
              </span>
            </div>
            {account.identifierPreview ? (
              <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>
                Saved account: <code>{account.identifierPreview}</code>
              </p>
            ) : null}
            {account.lastTestedAt ? (
              <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>
                Last tested: {new Date(account.lastTestedAt).toLocaleString()}
              </p>
            ) : null}
            {account.lastError ? (
              <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 10, padding: "10px 12px", fontSize: 12, color: "#9a3412", lineHeight: 1.5 }}>
                {account.lastError}
              </div>
            ) : null}
          </div>

          <div style={{ display: "grid", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6, display: "block", textTransform: "uppercase", letterSpacing: "0.08em" }}>Email / Username</label>
              <input
                value={account.email}
                onChange={(e) => onChange({ ...account, email: e.target.value })}
                placeholder="name@example.com or username"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6, display: "block", textTransform: "uppercase", letterSpacing: "0.08em" }}>Phone Number</label>
              <input
                value={account.phone}
                onChange={(e) => onChange({ ...account, phone: e.target.value })}
                placeholder="Optional fallback phone"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6, display: "block", textTransform: "uppercase", letterSpacing: "0.08em" }}>Password</label>
              <input
                type="password"
                value={account.password}
                onChange={(e) => onChange({ ...account, password: e.target.value })}
                placeholder="Stored encrypted on the backend"
                style={inputStyle}
              />
            </div>
            <p style={{ fontSize: 12, color: "#64748b", margin: 0, lineHeight: 1.7 }}>
              These credentials are encrypted server-side and are only used by the browser automation session. They are never returned to the UI after saving.
            </p>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <button onClick={onDelete} disabled={deleting} style={btnDanger}>
              {deleting ? <Loader2 size={13} /> : <Trash2 size={13} />} Remove saved account
            </button>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button onClick={onTest} disabled={testing || saving} style={btnSecondary}>
                {testing ? <Loader2 size={13} /> : <ShieldCheck size={13} />} Test connection
              </button>
              <button onClick={onSave} disabled={saving} style={btnPrimary}>
                {saving ? <Loader2 size={13} /> : <KeyRound size={13} />} Save credentials
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
