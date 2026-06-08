import type { ApiRecord, BillingPlan, Business, IntegrationAccount, IntegrationStatus, MarketingCampaign, PaymentTransaction, Product, SubscriptionSummary, User } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  headers?: HeadersInit;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 15000;

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method || "GET";
  const maxAttempts = method === "GET" ? 2 : 1;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (options.auth !== false && token) headers.Authorization = `Bearer ${token}`;

  let response: Response | null = null;
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    try {
      response = await fetch(`${API_URL}${path}`, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        cache: "no-store",
        signal: controller.signal,
      });
      break;
    } catch (error: any) {
      lastError = error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => globalThis.setTimeout(resolve, 350));
        continue;
      }
      if (error?.name === "AbortError") {
        throw new Error(`Request timed out after ${Math.round((options.timeoutMs ?? DEFAULT_TIMEOUT_MS) / 1000)}s: ${path}`);
      }
      throw new Error(error?.message || `Cannot connect to backend at ${API_URL}`);
    } finally {
      globalThis.clearTimeout(timeout);
    }
  }
  if (!response) throw new Error((lastError as Error)?.message || `Cannot connect to backend at ${API_URL}`);

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload ? (payload as ApiRecord).detail : payload;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail
          ? String((detail as ApiRecord).message || (detail as ApiRecord).error || `Request failed with ${response.status}`)
          : `Request failed with ${response.status}`;
    const error = new Error(message) as Error & ApiRecord;
    error.status = response.status;
    if (typeof detail === "object" && detail) {
      Object.assign(error, detail);
      error.detail = detail;
    }
    throw error;
  }

  return payload as T;
}

async function requestForm<T = any>(path: string, formData: FormData, options: Omit<RequestOptions, "body" | "headers"> = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (options.auth !== false && token) headers.Authorization = `Bearer ${token}`;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      method: options.method || "POST",
      headers,
      body: formData,
      cache: "no-store",
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === "object" && payload && "detail" in payload ? (payload as ApiRecord).detail : payload;
      const message =
        typeof detail === "string"
          ? detail
          : typeof detail === "object" && detail
            ? String((detail as ApiRecord).message || (detail as ApiRecord).error || `Request failed with ${response.status}`)
            : `Request failed with ${response.status}`;
      const error = new Error(message) as Error & ApiRecord;
      error.status = response.status;
      if (typeof detail === "object" && detail) {
        Object.assign(error, detail);
        error.detail = detail;
      }
      throw error;
    }
    return payload as T;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

const qs = (params: ApiRecord = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  const text = query.toString();
  return text ? `?${text}` : "";
};

export const api = {
  request,
  login: (payload: ApiRecord) => request("/auth/login", { method: "POST", body: payload, auth: false }),
  signup: (payload: ApiRecord) => request("/auth/signup", { method: "POST", body: payload, auth: false }),
  me: () => request<User>("/auth/me"),
  updateSettings: (payload: ApiRecord) => request("/auth/me", { method: "PATCH", body: payload }),
  getApiKeys: () => request("/auth/api-keys"),
  updateApiKeys: (payload: ApiRecord) => request("/auth/api-keys", { method: "POST", body: payload }),

  getActiveContext: () => request("/context/active"),
  setActiveContext: (payload: ApiRecord) => request("/context/active", { method: "PUT", body: payload }),
  createWorkspace: (payload: ApiRecord) => request("/workspaces", { method: "POST", body: payload }),

  listBusinesses: () => request<Business[]>("/businesses"),
  getProductIntelligence: () => request<ApiRecord>("/product-intelligence/report", { auth: false }),
  generateBusiness: (payload: ApiRecord) => request<Business>("/businesses/generate", { method: "POST", body: payload }),
  listProducts: (businessId?: string) => request<Product[]>(`/products${qs({ business_id: businessId })}`),
  createProduct: (payload: ApiRecord) => request<Product>("/products", { method: "POST", body: payload }),
  duplicateProduct: (productId: string) => request<Product>(`/products/${productId}/duplicate`, { method: "POST" }),
  deleteProduct: (productId: string) => request(`/products/${productId}`, { method: "DELETE" }),

  createCheckout: (payload: ApiRecord | string) => request<ApiRecord>("/payments/checkout", { method: "POST", body: typeof payload === "string" ? { product_id: payload } : payload, auth: false }),
  track: (payload: ApiRecord) => request("/analytics/track", { method: "POST", body: payload, auth: false }),
  getOperatingSummary: (businessId: string) => request(`/analytics/${businessId}/operating-summary`),
  optimize: (businessId: string) => request(`/optimize/${businessId}`),

  getSubscription: () => request<SubscriptionSummary>("/billing/subscription"),
  listBillingPlans: () => request<BillingPlan[]>("/billing/plans"),
  listPaymentTransactions: () => request<PaymentTransaction[]>("/billing/transactions"),
  createPayPalSubscription: (payload: ApiRecord | string) => request<ApiRecord>("/billing/paypal/create-subscription", { method: "POST", body: typeof payload === "string" ? { plan_slug: payload } : payload }),
  cancelPayPalSubscription: () => request("/billing/paypal/cancel-subscription", { method: "POST" }),
  createPayPalOrder: (payload: ApiRecord) => request("/billing/paypal/create-order", { method: "POST", body: payload }),

  listCampaigns: (businessId: string) => request<MarketingCampaign[]>(`/marketing/${businessId}/campaigns`),
  getCampaign: (businessId: string, campaignId: string) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/${campaignId}`),
  generateEmailCampaign: (businessId: string, payload: ApiRecord) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/email`, { method: "POST", body: payload }),
  generateSocialContent: (businessId: string, payload: ApiRecord) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/social`, { method: "POST", body: payload }),
  generateAdCampaign: (businessId: string, payload: ApiRecord) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/ads`, { method: "POST", body: payload }),
  generateSeoBlog: (businessId: string, payload: ApiRecord) => request(`/marketing/${businessId}/seo/generate`, { method: "POST", body: payload }),
  approveCampaign: (businessId: string, campaignId: string) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/${campaignId}/approve`, { method: "POST" }),
  rejectCampaign: (businessId: string, campaignId: string, reason?: string) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/${campaignId}/reject`, { method: "POST", body: reason ? { reason } : undefined }),
  updateCampaign: (businessId: string, campaignId: string, payload: ApiRecord) => request<MarketingCampaign>(`/marketing/${businessId}/campaigns/${campaignId}`, { method: "PATCH", body: payload }),
  publishCampaign: (businessId: string, campaignId: string, platform: string, payload?: ApiRecord) => request(`/marketing/${businessId}/campaigns/${campaignId}/publish/${platform}`, { method: "POST", body: payload }),
  sendEmailCampaign: (businessId: string, campaignId: string, recipientEmails: string[] = []) => request(`/marketing/${businessId}/campaigns/${campaignId}/send`, { method: "POST", body: { recipient_emails: recipientEmails } }),
  scheduleCampaign: (businessId: string, campaignId: string, scheduledAtOrPayload: string | ApiRecord, timezone?: string, platform?: string) => request(`/marketing/${businessId}/campaigns/${campaignId}/schedule`, { method: "POST", body: typeof scheduledAtOrPayload === "string" ? { scheduled_at: scheduledAtOrPayload, timezone, platform } : scheduledAtOrPayload }),
  generateCampaignImage: (businessId: string, campaignId: string, payload: ApiRecord = {}) => request(`/marketing/${businessId}/campaigns/${campaignId}/generate-image`, { method: "POST", body: payload }),
  optimizeCampaign: (businessId: string, campaignId: string) => request<ApiRecord>(`/marketing/${businessId}/campaigns/${campaignId}/optimize`),
  getCalendar: (businessId: string) => request(`/marketing/${businessId}/calendar`),
  getMarketingAnalytics: (businessId: string) => request(`/marketing/${businessId}/analytics`),
  listContacts: (businessId: string) => request<ApiRecord[]>(`/marketing/${businessId}/contacts`),
  createContact: (businessId: string, payload: ApiRecord) => request<ApiRecord>(`/marketing/${businessId}/contacts`, { method: "POST", body: payload }),
  importContactsCsv: (businessId: string, file: File) => {
    const formData = new FormData();
    formData.set("file", file);
    return requestForm<ApiRecord>(`/marketing/${businessId}/contacts/import-csv`, formData, { timeoutMs: 45000 });
  },
  generateContentStudioAsset: (businessId: string, payload: ApiRecord) => request<MarketingCampaign>(`/marketing/${businessId}/content-studio/generate`, { method: "POST", body: payload }),

  listCalendarEvents: (businessId: string) => request<ApiRecord[]>(`/calendar/events${qs({ business_id: businessId })}`),
  createCalendarEvent: (payload: ApiRecord) => request<ApiRecord>("/calendar/events", { method: "POST", body: payload }),
  syncGoogleCalendar: (businessId: string, daysAhead = 60) => request<ApiRecord>("/calendar/sync", { method: "POST", body: { business_id: businessId, days_ahead: daysAhead }, timeoutMs: 45000 }),

  getIntegrations: (businessId: string) => request<IntegrationStatus[]>(`/integrations/${businessId}`),
  listIntegrationAccounts: (businessId: string) => request<IntegrationAccount[]>(`/integrations/${businessId}/accounts`),
  connectIntegration: (businessId: string, platform: string) => request<ApiRecord>(`/integrations/${platform}/connect`, { method: "POST", body: { business_id: businessId } }),
  disconnectIntegration: (businessId: string, platform: string) => request(`/integrations/${businessId}/${platform}/disconnect`, { method: "POST" }),
  refreshIntegration: (businessId: string, platform: string) => request<ApiRecord>(`/integrations/${platform}/refresh${qs({ business_id: businessId })}`, { method: "POST" }),
  testOAuthIntegration: (businessId: string, platform: string) => request<ApiRecord>(`/integrations/${platform}/test${qs({ business_id: businessId })}`, { method: "POST" }),
  listIntegrationActionLogs: (businessId: string, platform?: string, limit = 30) => request<ApiRecord[]>(`/integrations/actions/logs${qs({ business_id: businessId, platform, limit })}`),
  sendGmailTool: (businessId: string, payload: ApiRecord) => request<ApiRecord>(`/tools/gmail/send${qs({ business_id: businessId })}`, { method: "POST", body: payload }),
  sendSendGridTool: (businessId: string, payload: ApiRecord) => request<ApiRecord>(`/tools/sendgrid/send${qs({ business_id: businessId })}`, { method: "POST", body: payload }),
  createNotionPageTool: (businessId: string, payload: ApiRecord) => request<ApiRecord>(`/tools/notion/page${qs({ business_id: businessId })}`, { method: "POST", body: payload }),
  connectWithApiKey: (businessId: string, platform: string, payload: ApiRecord | string) => request(`/integrations/${businessId}/${platform}/connect-apikey`, { method: "POST", body: typeof payload === "string" ? { api_key: payload } : payload }),
  saveIntegrationAccount: (businessId: string, platform: string, payload: ApiRecord) => request<IntegrationAccount>(`/integrations/${businessId}/accounts/${platform}`, { method: "PUT", body: payload }),
  testIntegrationAccount: (businessId: string, platform: string) => request<IntegrationAccount>(`/integrations/${businessId}/accounts/${platform}/test`, { method: "POST" }),
  deleteIntegrationAccount: (businessId: string, platform: string) => request(`/integrations/${businessId}/accounts/${platform}`, { method: "DELETE" }),
  listCredentials: (businessId?: string) => request(`/credentials${qs({ business_id: businessId })}`),
  saveCredential: (provider: string, payload: ApiRecord) => request(`/credentials/${provider}`, { method: "POST", body: payload }),
  testCredentialLogin: (provider: string, businessId?: string) => request(`/credentials/${provider}/test-login${qs({ business_id: businessId })}`, { method: "POST" }),
  deleteCredential: (provider: string, businessId?: string) => request(`/credentials/${provider}${qs({ business_id: businessId })}`, { method: "DELETE" }),

  getBrandSystem: (businessId: string) => request(`/brand/${businessId}`),
  saveBrandSystem: (businessId: string, payload: ApiRecord) => request(`/brand/${businessId}`, { method: "POST", body: payload }),
  listSupportConversations: (businessId: string, status?: string) => request<Array<{
    id: string;
    visitor_token: string;
    status: string;
    messages: { role: string; content: string }[];
    summary: string | null;
    created_at: string;
  }>>(`/support/${businessId}/conversations${qs({ conv_status: status })}`),
  resolveConversation: (businessId: string, conversationId: string) => request(`/support/${businessId}/conversations/${conversationId}/resolve`, { method: "PATCH" }),

  runAgentController: (payload: ApiRecord) => request("/agent/run", { method: "POST", body: payload }),
  runBrowserAgent: (payload: ApiRecord) => request("/agent/browser/run", { method: "POST", body: payload }),
  controlBrowserRun: (runId: string, action: string, steps?: number) => request(`/agent/browser/runs/${runId}/control`, { method: "POST", body: { action, steps } }),
  listAgentReports: (businessId: string, limit = 20) => request(`/agent/reports${qs({ business_id: businessId, limit })}`),
  createMarketingBriefFromAgentReport: (businessId: string, reportId: string) => request(`/agent/reports/${reportId}/marketing-brief`, { method: "POST", body: { business_id: businessId } }),

  listStudioHistory: (businessId: string) => request(`/code-editor/history${qs({ business_id: businessId })}`),
  revertStudioVersion: (versionId: string, businessId?: string) => request(`/code-editor/revert`, { method: "POST", body: { business_id: businessId, version_id: versionId } }),
  deleteStudioVersion: (versionId: string, businessId?: string) => request(`/code-editor/version${qs({ business_id: businessId, version_id: versionId })}`, { method: "DELETE" }),
};

export { request as apiRequest };
