"use client";
/**
 * Fast data hooks using SWR — replaces manual fetch() calls.
 * Data is cached for 5 minutes. Instant navigation between pages.
 *
 * Usage:
 *   const { data: businesses, isLoading } = useBusinesses();
 *   const { data: campaigns } = useCampaigns(businessId);
 */
import useSWR from "swr";
import { fetcher } from "@/lib/swr-config";

// ── Businesses ────────────────────────────────────────────────────────────────
export function useBusinesses() {
  return useSWR("/businesses", fetcher, {
    dedupingInterval: 5 * 60 * 1000, // 5 min cache
  });
}

// ── Products ──────────────────────────────────────────────────────────────────
export function useProducts(businessId?: string) {
  const key = businessId ? `/products?business_id=${businessId}` : "/products";
  return useSWR(key, fetcher, {
    dedupingInterval: 2 * 60 * 1000,
  });
}

// ── Analytics ─────────────────────────────────────────────────────────────────
export function useAnalytics(businessId?: string) {
  return useSWR(
    businessId ? `/analytics/${businessId}` : null,
    fetcher,
    { dedupingInterval: 60 * 1000 } // 1 min — analytics change often
  );
}

export function useAnalyticsDashboard(businessId?: string) {
  return useSWR(
    businessId ? `/analytics/${businessId}/dashboard` : null,
    fetcher,
    { dedupingInterval: 60 * 1000 }
  );
}

// ── Campaigns ─────────────────────────────────────────────────────────────────
export function useCampaigns(businessId?: string) {
  return useSWR(
    businessId ? `/marketing/${businessId}/campaigns` : null,
    fetcher,
    { dedupingInterval: 30 * 1000 } // 30s — campaigns update frequently
  );
}

export function useSeoContent(businessId?: string) {
  return useSWR(
    businessId ? `/marketing/${businessId}/seo` : null,
    fetcher,
    { dedupingInterval: 60 * 1000 }
  );
}

// ── AI Telemetry ──────────────────────────────────────────────────────────────
export function useTelemetryHealth() {
  return useSWR("/ai/telemetry/health", fetcher, {
    refreshInterval: 7000, // auto-refresh every 7s
    dedupingInterval: 5000,
  });
}

// ── Integrations ──────────────────────────────────────────────────────────────
export function useIntegrations(businessId?: string) {
  return useSWR(
    businessId ? `/integrations/${businessId}` : null,
    fetcher,
    { dedupingInterval: 60 * 1000 }
  );
}

// ── Brand System ──────────────────────────────────────────────────────────────
export function useBrandSystem(businessId?: string) {
  return useSWR(
    businessId ? `/brand/${businessId}` : null,
    fetcher,
    { dedupingInterval: 5 * 60 * 1000 }
  );
}

// ── Support Conversations ─────────────────────────────────────────────────────
export function useSupportConversations(businessId?: string, status?: string) {
  const key = businessId
    ? `/support/${businessId}/conversations${status ? `?conv_status=${status}` : ""}`
    : null;
  return useSWR(key, fetcher, { dedupingInterval: 30 * 1000 });
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
export function useJobs() {
  return useSWR("/jobs/?limit=20", fetcher, {
    refreshInterval: 5000, // poll every 5s for running jobs
    dedupingInterval: 3000,
  });
}

// ── Usage ─────────────────────────────────────────────────────────────────────
export function useUsage() {
  return useSWR("/usage/my-usage", fetcher, {
    dedupingInterval: 5 * 60 * 1000,
  });
}
