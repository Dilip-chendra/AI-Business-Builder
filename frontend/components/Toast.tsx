"use client";

import { useEffect, useState, createContext, useContext, useCallback } from "react";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, duration?: number) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const STYLES: Record<ToastType, { bg: string; border: string; color: string; icon: string }> = {
  success: { bg: "#f0fdf4", border: "#bbf7d0", color: "#16a34a", icon: "#10b981" },
  error:   { bg: "#fef2f2", border: "#fecaca", color: "#dc2626", icon: "#ef4444" },
  warning: { bg: "#fffbeb", border: "#fde68a", color: "#d97706", icon: "#f59e0b" },
  info:    { bg: "#eff6ff", border: "#bfdbfe", color: "#2563eb", icon: "#3b82f6" },
};

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
  const [visible, setVisible] = useState(false);
  const s = STYLES[toast.type];
  const Icon = ICONS[toast.type];

  useEffect(() => {
    // Animate in
    const t1 = setTimeout(() => setVisible(true), 10);
    // Auto-remove
    const duration = toast.duration ?? 4000;
    const t2 = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onRemove(toast.id), 300);
    }, duration);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [toast.id, toast.duration, onRemove]);

  return (
    <div
      style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        background: s.bg, border: `1px solid ${s.border}`,
        borderRadius: 12, padding: "12px 14px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
        maxWidth: 380, width: "100%",
        transform: visible ? "translateX(0)" : "translateX(120%)",
        opacity: visible ? 1 : 0,
        transition: "transform 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.3s ease",
        pointerEvents: "all",
      }}
    >
      <Icon size={16} style={{ color: s.icon, flexShrink: 0, marginTop: 1 }} />
      <p style={{ fontSize: 13, color: s.color, margin: 0, flex: 1, lineHeight: 1.5, fontWeight: 500 }}>
        {toast.message}
      </p>
      <button
        onClick={() => { setVisible(false); setTimeout(() => onRemove(toast.id), 300); }}
        style={{ background: "none", border: "none", cursor: "pointer", color: s.color, opacity: 0.6, padding: 0, flexShrink: 0 }}
      >
        <X size={14} />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const add = useCallback((message: string, type: ToastType = "info", duration = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts(prev => [...prev.slice(-4), { id, type, message, duration }]); // max 5
  }, []);

  const value: ToastContextValue = {
    toast: add,
    success: (m) => add(m, "success"),
    error:   (m) => add(m, "error", 6000),
    warning: (m) => add(m, "warning"),
    info:    (m) => add(m, "info"),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Toast container */}
      <div
        style={{
          position: "fixed", top: 20, right: 20, zIndex: 9999,
          display: "flex", flexDirection: "column", gap: 8,
          pointerEvents: "none",
        }}
      >
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onRemove={remove} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
