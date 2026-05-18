export type Business = {
  id: string;
  workspace_id?: string | null;
  project_id?: string | null;
  name: string;
  niche: string;
  description: string;
  target_audience: string;
  monetization_model: string;
  brand_tone: string;
  headline: string;
  subheading: string;
  product_pitch: string;
  cta_text: string;
  seo_title: string;
  seo_description: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
  // Rich AI-generated page content
  page_content?: {
    pain_points?: string[];
    benefits?: string[];
    features?: Array<{ title: string; description: string; icon_hint: string }>;
    social_proof?: Array<{ name: string; role: string; quote: string; rating: number }>;
    faq?: Array<{ question: string; answer: string }>;
    pricing_tiers?: Array<{
      name: string;
      price: string;
      period: string;
      features: string[];
      cta: string;
      highlighted: boolean;
    }>;
    urgency_text?: string;
    trust_badges?: string[];
    color_scheme?: string;
  };
};

export type Product = {
  id: string;
  business_id: string;
  project_id?: string | null;
  name: string;
  description: string;
  price: string;
  currency: string;
  category: string;
  status?: string;
  product_type?: string;
  image_url?: string | null;
  purchase_link?: string | null;
  stripe_price_id?: string | null;
  payment_provider?: string | null;
  paypal_product_id?: string | null;
  paypal_plan_id?: string | null;
  paypal_checkout_url?: string | null;
  billing_type?: string;
  created_at?: string;
  updated_at?: string;
};

export type MarketingCampaign = {
  id: string;
  business_id: string;
  product_id?: string | null;
  project_id?: string | null;
  campaign_type: string;
  name: string;
  status: string;
  content: Record<string, any>;
  targeting: Record<string, any>;
  metrics: Record<string, any>;
  approved_by?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  image_url?: string | null;
  lifecycle_status?: string;
  scheduled_at?: string | null;
};

export type IntegrationStatus = {
  platform: string;
  status: string;
  account_name: string | null;
  account_id?: string | null;
  has_oauth?: boolean;
  state_label?: "not_configured" | "ready_to_connect" | "connected" | "expired" | "disconnected" | "error";
  ready_to_connect?: boolean;
  connect_mode?: string;
  redirect_uri?: string;
  required_env_vars?: string[];
  scopes?: string[];
  connection_error?: string | null;
};

export type IntegrationProviderSettings = {
  platform: string;
  provider_name: string;
  connect_mode: string;
  redirect_uri?: string | null;
  required_env_vars: string[];
  scopes: string[];
  client_id_configured: boolean;
  client_secret_configured: boolean;
  client_id_preview?: string | null;
  ready_to_connect: boolean;
  message: string;
};

export type IntegrationAccount = {
  id: string | null;
  platform: string;
  status: string;
  identifier_preview: string;
  last_active_at: string | null;
  last_tested_at: string | null;
  last_error: string | null;
};

export type StudioVersionRecord = {
  id: string;
  file_path: string;
  source: string;
  instruction?: string | null;
  version_number: number;
  content_preview: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Workspace = {
  id: string;
  name: string;
  slug: string;
  owner_id?: string;
  created_at?: string | null;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  type: string;
  template_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ActiveContext = {
  workspace_id: string | null;
  business_id: string | null;
  project_id: string | null;
};

export type ContextHierarchy = {
  active: ActiveContext;
  workspaces: Workspace[];
  businesses: Business[];
  projects: Project[];
};

export type BillingPlan = {
  id: string;
  name: string;
  slug: string;
  description: string;
  price_cents: number;
  currency: string;
  interval: string;
  features_json: Record<string, unknown>;
  limits_json: Record<string, number | null>;
  is_active: boolean;
};

export type UsageSummary = {
  feature_key: string;
  used: number;
  limit: number | null;
  remaining: number | null;
  unlimited: boolean;
};

export type SubscriptionSummary = {
  subscription_id: string | null;
  provider: string;
  provider_subscription_id: string | null;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  plan: BillingPlan;
  usage: UsageSummary[];
};

export type PaymentTransaction = {
  id: string;
  provider: string;
  provider_payment_id?: string | null;
  provider_order_id?: string | null;
  provider_subscription_id?: string | null;
  amount_cents: number;
  currency: string;
  status: string;
  type: string;
  created_at: string;
};

export type AnalyticsSummary = {
  business_id: string;
  visitors: number;
  clicks: number;
  conversions: number;
  revenue_cents: number;
  conversion_rate: number;
  product_performance: Array<{
    product_id: string | null;
    events: number;
    revenue_cents: number;
  }>;
};

export type AnalyticsDashboard = {
  business_id: string;
  ai_requests: number;
  campaigns_generated: number;
  success_rate: number;
  usage_over_time: Array<{
    date: string;
    ai_requests: number;
    campaigns_generated: number;
  }>;
};

export type OptimizationSuggestion = {
  headline: string | null;
  cta_text: string | null;
  pricing_note: string | null;
  positioning_note: string | null;
};

export type AIHealth = {
  groq: boolean;
  huggingface: boolean;
  ollama: boolean;
  any_available: boolean;
};

export type AgentLog = {
  id: string;
  business_id: string;
  agent_type: string;
  log_type: string;
  summary: string;
  payload: Record<string, unknown>;
  applied: boolean;
  created_at: string;
};
