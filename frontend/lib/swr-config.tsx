"use client";
import { SWRConfig } from "swr";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Global fetcher with JWT auth
export async function fetcher(path: string) {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// SWR provider — wrap your app with this for global caching
export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        // Cache data for 5 minutes — avoids refetching on every navigation
        dedupingInterval: 5 * 60 * 1000,
        // Revalidate in background when window regains focus
        revalidateOnFocus: false,
        // Don't retry on error by default
        shouldRetryOnError: false,
        // Keep stale data while revalidating (instant navigation)
        keepPreviousData: true,
      }}
    >
      {children}
    </SWRConfig>
  );
}
