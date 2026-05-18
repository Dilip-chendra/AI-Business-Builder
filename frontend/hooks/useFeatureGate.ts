"use client";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type GateResult = {
  allowed: boolean;
  tier: string;
  required_tier: string;
  feature: string;
};

const TIER_LABELS: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function useFeatureGate(feature: string): {
  allowed: boolean | null;
  tier: string;
  requiredTier: string;
  loading: boolean;
} {
  const [result, setResult] = useState<GateResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!feature) { setLoading(false); return; }
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) { setLoading(false); return; }

    fetch(`${API_URL}/usage/check-gate?feature=${encodeURIComponent(feature)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setResult(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [feature]);

  return {
    allowed: result?.allowed ?? null,
    tier: TIER_LABELS[result?.tier || "free"] || "Free",
    requiredTier: TIER_LABELS[result?.required_tier || "pro"] || "Pro",
    loading,
  };
}
