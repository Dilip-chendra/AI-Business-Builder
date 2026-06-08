export type ApiRecord = Record<string, any>;

export type User = {
  id: string;
  email: string;
  full_name?: string | null;
  is_active?: boolean;
  is_verified?: boolean;
  stripe_publishable_key?: string | null;
  created_at?: string;
};

export type Business = ApiRecord & {
  id: string;
  name: string;
  niche?: string | null;
  description?: string | null;
  workspace_id?: string | null;
  project_id?: string | null;
};

export type Product = ApiRecord & {
  id: string;
  business_id?: string;
  name: string;
  price?: number;
};

export type MarketingCampaign = ApiRecord & {
  id: string;
  business_id?: string;
  title?: string;
  status?: string;
  platform?: string;
};

export type IntegrationProviderSettings = ApiRecord;
export type IntegrationStatus = ApiRecord;
export type IntegrationAccount = ApiRecord & {
  id?: string | null;
  platform: string;
  status: string;
};

export type BillingPlan = ApiRecord & {
  id: string;
  name: string;
  slug: string;
  price_cents: number;
  interval: string;
  features_json: ApiRecord;
  limits_json: ApiRecord;
};

export type UsageSummary = ApiRecord & {
  feature_key: string;
  used: number;
  limit: number | null;
  unlimited?: boolean;
};

export type PaymentTransaction = ApiRecord & {
  id: string;
  amount_cents: number;
  status: string;
  type: string;
  created_at: string;
};

export type SubscriptionSummary = ApiRecord & {
  plan: BillingPlan;
  usage: UsageSummary[];
  status: string;
};

export type StudioVersionRecord = ApiRecord & {
  id: string;
  business_id?: string;
  filename?: string;
  created_at?: string;
};
