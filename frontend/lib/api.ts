import type {
  ActiveContext,
  AnalyticsDashboard,
  AnalyticsSummary,
  BillingPlan,
  Business,
  ContextHierarchy,
  MarketingCampaign,
  IntegrationStatus,
  IntegrationProviderSettings,
  IntegrationAccount,
  OptimizationSuggestion,
  PaymentTransaction,
  Product,
  Project,
  StudioVersionRecord,
  SubscriptionSummary,
  Workspace,
} from "@/lib/types";

const serviceApiBase = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.trim() ||
  (serviceApiBase ? `${serviceApiBase}/v1` : "http://localhost:8000/api/v1");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> || {}),
  };

  // Attach JWT from localStorage when running in the browser
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  }).catch((networkErr: Error) => {
    // Network error — backend is down or CORS blocked
    throw new Error(
      `Cannot connect to the server. Make sure the backend is running at ${API_URL}. (${networkErr.message})`
    );
  });

  if (!response.ok) {
    // Try to extract a human-readable detail from the JSON body
    let detail = `Request failed with status ${response.status}`;
    let body: any = null;
    try {
      body = await response.json();
      if (body?.detail) {
        detail = typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
      }
    } catch {
      // body wasn't JSON — use the status text
      detail = response.statusText || detail;
    }
    // Prefix 503 errors so the UI can detect AI unavailability
    if (response.status === 503) {
      throw new Error(`503: ${detail}`);
    }
    if (response.status === 401) {
      // Clear stale token and redirect to login
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
      throw new Error(`401: ${detail}`);
    }
    const err = new Error(detail) as Error & { status?: number; detail?: unknown };
    err.status = response.status;
    err.detail = body?.detail ?? detail;
    throw err;
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  login: (payload: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  signup: (payload: { email: string; password: string; full_name?: string }) =>
    request<{ access_token: string; token_type: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  me: () => request<any>("/auth/me"),

  updateSettings: (payload: Partial<{ full_name: string; stripe_publishable_key: string }>) =>
    request<any>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) }),

  getApiKeys: () => request<any>("/auth/api-keys"),

  updateApiKeys: (payload: any) =>
    request<any>("/auth/api-keys", { method: "POST", body: JSON.stringify(payload) }),

  // Context
  getActiveContext: () => request<ContextHierarchy>("/context/active"),

  setActiveContext: (payload: Partial<ActiveContext>) =>
    request<{ active: ActiveContext }>("/context/active", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  listWorkspaces: () => request<Workspace[]>("/workspaces"),

  createWorkspace: (payload: { name: string }) =>
    request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify(payload) }),

  listProjects: (workspaceId: string) =>
    request<Project[]>(`/workspaces/${workspaceId}/projects`),

  createProject: (workspaceId: string, payload: { name: string; type?: string }) =>
    request<Project>(`/workspaces/${workspaceId}/projects`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ── Businesses ────────────────────────────────────────────────────────────
  listBusinesses: (params?: { workspace_id?: string; project_id?: string }) =>
    request<Business[]>(
      `/businesses${
        params?.workspace_id || params?.project_id
          ? `?${new URLSearchParams(
              Object.entries(params).filter(([, value]) => Boolean(value)) as [string, string][]
            ).toString()}`
          : ""
      }`
    ),

  getBusiness: (id: string) => request<Business>(`/businesses/${id}`),

  generateBusiness: (payload: {
    interests: string;
    niche_preferences?: string;
    target_audience?: string;
    goals?: string;
  }) =>
    request<Business>("/businesses/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ── Products ──────────────────────────────────────────────────────────────
  listProducts: (businessId?: string) =>
    request<Product[]>(`/products${businessId ? `?business_id=${businessId}` : ""}`),

  createProduct: (payload: Omit<Product, "id" | "created_at" | "updated_at">) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(payload) }),

  updateProduct: (id: string, payload: Partial<Product>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),

  duplicateProduct: (id: string) =>
    request<Product>(`/products/${id}/duplicate`, { method: "POST" }),

  deleteProduct: (id: string) =>
    request<void>(`/products/${id}`, { method: "DELETE" }),

  // ── Payments ──────────────────────────────────────────────────────────────
  createCheckout: (productId: string) =>
    request<{ checkout_url: string; session_id: string }>("/payments/checkout", {
      method: "POST",
      body: JSON.stringify({ product_id: productId }),
    }),

  // Billing / PayPal
  listBillingPlans: () => request<BillingPlan[]>("/billing/plans"),

  getSubscription: () => request<SubscriptionSummary>("/billing/subscription"),

  listPaymentTransactions: () => request<PaymentTransaction[]>("/billing/transactions"),

  createPayPalSubscription: (planSlug: "pro_monthly" | "pro_yearly" | "team_monthly") =>
    request<{ paypal_subscription_id: string; approval_url: string }>("/billing/paypal/create-subscription", {
      method: "POST",
      body: JSON.stringify({ plan_slug: planSlug }),
    }),

  cancelPayPalSubscription: () =>
    request<{ status: string; subscription_id: string | null }>("/billing/paypal/cancel-subscription", {
      method: "POST",
    }),

  createPayPalOrder: (payload: { product_id: string; business_id?: string }) =>
    request<{ order_id: string; approval_url: string }>("/billing/paypal/create-order", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  capturePayPalOrder: (orderId: string) =>
    request<PaymentTransaction>("/billing/paypal/capture-order", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId }),
    }),

  // ── Analytics ─────────────────────────────────────────────────────────────
  track: (payload: {
    business_id: string;
    product_id?: string;
    event_type: string;
    source?: string;
    value_cents?: number;
    metadata_json?: object;
  }) =>
    request<{ status: string }>("/analytics/track", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  analytics: (businessId: string) =>
    request<AnalyticsSummary>(`/analytics/${businessId}`),

  analyticsDashboard: (businessId: string) =>
    request<AnalyticsDashboard>(`/analytics/${businessId}/dashboard`),

  // ── AI ────────────────────────────────────────────────────────────────────
  aiHealth: () =>
    request<{ featherless: boolean; groq: boolean; huggingface: boolean; ollama: boolean; any_available: boolean }>(
      "/ai/health"
    ),

  featherlessHealth: () =>
    request<{ ok: boolean; configured: boolean; reason?: string; model?: string; usage?: Record<string, unknown> }>(
      "/ai/providers/featherless/health"
    ),

  testFeatherless: (prompt: string) =>
    request<{ ok: boolean; provider: string; model?: string; output: string }>(
      "/ai/providers/featherless/test",
      { method: "POST", body: JSON.stringify({ prompt }) }
    ),

  optimize: (businessId: string) =>
    request<OptimizationSuggestion>(`/optimize/${businessId}`),

  // ── Agents ────────────────────────────────────────────────────────────────
  runAgentPipeline: (businessId: string, applyDecisions = false) =>
    request<any>(`/agents/${businessId}/run`, {
      method: "POST",
      body: JSON.stringify({ apply_decisions: applyDecisions }),
    }),

  agentLogs: (businessId: string) =>
    request<any[]>(`/agents/${businessId}/logs`),

  // ── Autonomous Agent Controller ───────────────────────────────────────────
  runAgentController: (payload: {
    goal: string;
    business_id?: string;
    apply_actions?: boolean;
    use_browser?: boolean;
    max_steps?: number;
  }) =>
    request<any>("/agent/run", { method: "POST", body: JSON.stringify(payload) }),

  runBrowserAgent: (payload: { goal: string; business_id?: string }) =>
    request<any>("/agent/browser/run", { method: "POST", body: JSON.stringify(payload) }),

  getAgentRunStatus: (runId: string) =>
    request<any>(`/agent/status/${runId}`),

  getAgentRunLogs: (runId: string) =>
    request<any>(`/agent/logs/${runId}`),

  // ── Experiments ───────────────────────────────────────────────────────────
  createExperiment: (payload: { business_id: string; name: string; description?: string }) =>
    request<any>("/experiments", { method: "POST", body: JSON.stringify(payload) }),

  listExperiments: (businessId: string) =>
    request<any[]>(`/experiments/business/${businessId}`),

  // ── Marketing Engine ──────────────────────────────────────────────────────
  generateSeoBlog: (businessId: string, payload: { topic: string; target_keyword: string }) =>
    request<any>(`/marketing/${businessId}/seo/generate`, { method: "POST", body: JSON.stringify(payload) }),

  listSeoContent: (businessId: string) =>
    request<any[]>(`/marketing/${businessId}/seo`),

  publishSeoContent: (businessId: string, contentId: string) =>
    request<any>(`/marketing/${businessId}/seo/${contentId}/publish`, { method: "PATCH" }),

  generateEmailCampaign: (businessId: string, payload: { name: string; goal: string; recipient_count?: number; product_id?: string }) =>
    request<MarketingCampaign>(`/marketing/${businessId}/campaigns/email`, { method: "POST", body: JSON.stringify(payload) }),

  generateSocialContent: (businessId: string, payload: { platform: string; post_count?: number; product_id?: string }) =>
    request<MarketingCampaign>(`/marketing/${businessId}/campaigns/social`, { method: "POST", body: JSON.stringify(payload) }),

  generateAdCampaign: (businessId: string, payload: { platform: string; budget_usd: number; product_id?: string }) =>
    request<MarketingCampaign>(`/marketing/${businessId}/campaigns/ads`, { method: "POST", body: JSON.stringify(payload) }),

  listCampaigns: (businessId: string, campaignType?: string) =>
    request<MarketingCampaign[]>(`/marketing/${businessId}/campaigns${campaignType ? `?campaign_type=${campaignType}` : ""}`),

  approveCampaign: (businessId: string, campaignId: string) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/approve`, { method: "POST" }),

  rejectCampaign: (businessId: string, campaignId: string, reason: string) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/reject`, {
      method: "POST", body: JSON.stringify({ reason }),
    }),

  sendEmailCampaign: (businessId: string, campaignId: string, recipientEmails: string[]) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/send`, {
      method: "POST", body: JSON.stringify({ recipient_emails: recipientEmails }),
    }),

  // ── Customer Support ──────────────────────────────────────────────────────
  startSupportConversation: (businessId: string, visitorToken: string) =>
    request<any>(`/support/${businessId}/conversations`, {
      method: "POST", body: JSON.stringify({ visitor_token: visitorToken }),
    }),

  sendSupportMessage: (businessId: string, conversationId: string, message: string) =>
    request<any>(`/support/${businessId}/conversations/${conversationId}/message`, {
      method: "POST", body: JSON.stringify({ message }),
    }),

  listSupportConversations: (businessId: string, convStatus?: string) =>
    request<any[]>(`/support/${businessId}/conversations${convStatus ? `?conv_status=${convStatus}` : ""}`),

  resolveConversation: (businessId: string, conversationId: string) =>
    request<any>(`/support/${businessId}/conversations/${conversationId}/resolve`, { method: "PATCH" }),

  // ── Platform Integrations ─────────────────────────────────────────────────
  getIntegrations: (businessId: string) =>
    request<IntegrationStatus[]>(`/integrations/${businessId}`),

  connectIntegration: (businessId: string, platform: string) =>
    request<{ platform: string; type: string; auth_url?: string; message: string; provider_name?: string; redirect_uri?: string; required_env_vars?: string[]; scopes?: string[]; ready_to_connect?: boolean }>(
      `/integrations/${platform}/connect`,
      {
        method: "POST",
        body: JSON.stringify({ business_id: businessId }),
      }
    ),

  getIntegrationProviderSettings: (platform: string) =>
    request<IntegrationProviderSettings>(`/integrations/providers/${platform}/settings`),

  saveIntegrationProviderSettings: (platform: string, payload: { client_id: string; client_secret: string }) =>
    request<IntegrationProviderSettings>(`/integrations/providers/${platform}/settings`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listIntegrationAccounts: (businessId: string) =>
    request<IntegrationAccount[]>(`/integrations/${businessId}/accounts`),

  saveIntegrationAccount: (
    businessId: string,
    platform: string,
    payload: { email?: string; phone?: string; password?: string }
  ) =>
    request<IntegrationAccount>(`/integrations/${businessId}/accounts/${platform}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  testIntegrationAccount: (businessId: string, platform: string) =>
    request<IntegrationAccount>(`/integrations/${businessId}/accounts/${platform}/test`, {
      method: "POST",
    }),

  deleteIntegrationAccount: (businessId: string, platform: string) =>
    request<{ status: string; platform: string }>(`/integrations/${businessId}/accounts/${platform}`, {
      method: "DELETE",
    }),

  connectWithApiKey: (businessId: string, platform: string, apiKey: string, accountId?: string, accountName?: string) =>
    request<any>(`/integrations/${businessId}/${platform}/connect-apikey`, {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey, account_id: accountId, account_name: accountName }),
    }),

  disconnectIntegration: (businessId: string, platform: string) =>
    request<any>(`/integrations/${businessId}/${platform}/disconnect`, { method: "POST" }),

  // ── Brand System ──────────────────────────────────────────────────────────
  getBrandSystem: (businessId: string) =>
    request<any>(`/brand/${businessId}`),

  saveBrandSystem: (businessId: string, data: {
    primary_color?: string;
    secondary_color?: string;
    tone_of_voice?: string;
    target_audience?: string;
    industry?: string;
    competitors?: string[];
    website_url?: string;
    logo_description?: string;
  }) =>
    request<any>(`/brand/${businessId}`, { method: "POST", body: JSON.stringify(data) }),

  // ── Campaign Publishing & Scheduling ──────────────────────────────────────
  publishCampaign: (businessId: string, campaignId: string, platform: string) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/publish/${platform}`, {
      method: "POST",
    }),

  scheduleCampaign: (businessId: string, campaignId: string, scheduledAt: string, timezone: string, platform: string) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/schedule`, {
      method: "POST",
      body: JSON.stringify({ scheduled_at: scheduledAt, timezone, platform }),
    }),

  generateCampaignImage: (businessId: string, campaignId: string) =>
    request<{ image_url: string; campaign_id: string }>(
      `/marketing/${businessId}/campaigns/${campaignId}/generate-image`,
      { method: "POST" }
    ),

  // ── Marketing Calendar & Analytics ────────────────────────────────────────
  getCalendar: (businessId: string) =>
    request<any[]>(`/marketing/${businessId}/calendar`),

  getMarketingAnalytics: (businessId: string) =>
    request<any>(`/marketing/${businessId}/analytics`),

  recordCampaignMetrics: (businessId: string, campaignId: string, metrics: {
    impressions?: number;
    clicks?: number;
    conversions?: number;
    spend_cents?: number;
    engagement?: number;
    platform?: string;
  }) =>
    request<any>(`/marketing/${businessId}/campaigns/${campaignId}/metrics`, {
      method: "POST",
      body: JSON.stringify(metrics),
    }),

  controlBrowserRun: (runId: string, action: "pause" | "resume" | "continue" | "extend" | "force_final" | "stop" | "confirm_publish", steps?: number) =>
    request<{ run_id: string; status: string; action: string; steps_requested?: number | null }>(`/agent/browser/runs/${runId}/control`, {
      method: "POST",
      body: JSON.stringify({ action, steps }),
    }),

  listStudioHistory: (businessId: string, limit = 100) =>
    request<StudioVersionRecord[]>(`/code-editor/history?business_id=${businessId}&limit=${limit}`),

  deleteStudioVersion: (versionId: string) =>
    request<{ status: string; version_id: string }>(`/code-editor/version`, {
      method: "DELETE",
      body: JSON.stringify({ version_id: versionId }),
    }),

  revertStudioVersion: (versionId: string, businessId: string) =>
    request<{ status: string; path: string; restored_version_id: string; restored_version_number: number }>(`/code-editor/revert`, {
      method: "POST",
      body: JSON.stringify({ version_id: versionId, business_id: businessId }),
    }),
};
