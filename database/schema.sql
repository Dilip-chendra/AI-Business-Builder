-- Autonomous Business Builder — complete PostgreSQL schema
-- Run this in the Supabase SQL editor (or via psql) on a fresh database.
-- For incremental updates use Alembic: alembic upgrade head

create extension if not exists "pgcrypto";

-- ── users ─────────────────────────────────────────────────────────────────────
create table if not exists users (
  id               uuid primary key default gen_random_uuid(),
  email            varchar(255) not null unique,
  full_name        varchar(160),
  hashed_password  varchar(255),
  is_active        boolean not null default true,
  is_verified      boolean not null default false,
  stripe_publishable_key varchar(255),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists ix_users_email on users(email);

-- ── user_ai_settings ──────────────────────────────────────────────────────────
create table if not exists user_ai_settings (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null unique references users(id) on delete cascade,
  provider          varchar(40) not null default 'local',
  api_key_encrypted text,
  model_name        varchar(100),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists ix_user_ai_settings_user_id on user_ai_settings(user_id);

-- ── user_ai_settings ──────────────────────────────────────────────────────────
create table if not exists user_ai_settings (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null unique references users(id) on delete cascade,
  provider          varchar(40) not null default 'local',
  api_key_encrypted text,
  model_name        varchar(100),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists ix_user_ai_settings_user_id on user_ai_settings(user_id);

-- ── businesses ────────────────────────────────────────────────────────────────
create table if not exists businesses (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid references users(id) on delete set null,
  name                varchar(120) not null,
  niche               varchar(140) not null,
  description         text not null,
  target_audience     varchar(220) not null,
  monetization_model  varchar(160) not null,
  brand_tone          varchar(120) not null default 'clear and trustworthy',
  headline            varchar(180) not null,
  subheading          text not null,
  product_pitch       text not null,
  cta_text            varchar(80) not null default 'Start now',
  seo_title           varchar(180) not null,
  seo_description     varchar(260) not null,
  raw_ai_payload      jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index if not exists ix_businesses_user_id on businesses(user_id);

-- ── products ──────────────────────────────────────────────────────────────────
create table if not exists products (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid not null references businesses(id) on delete cascade,
  name             varchar(140) not null,
  description      text not null,
  price            numeric(10, 2) not null check (price > 0),
  currency         varchar(3) not null default 'usd',
  category         varchar(100) not null default 'digital',
  image_url        varchar(500),
  purchase_link    varchar(500),
  stripe_price_id  varchar(255),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists ix_products_business_id on products(business_id);

-- ── analytics_events ──────────────────────────────────────────────────────────
create table if not exists analytics_events (
  id            uuid primary key default gen_random_uuid(),
  business_id   uuid not null references businesses(id) on delete cascade,
  product_id    uuid references products(id) on delete set null,
  event_type    varchar(80) not null,
  source        varchar(120),
  value_cents   integer not null default 0 check (value_cents >= 0),
  metadata_json jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists ix_analytics_events_business_id on analytics_events(business_id);
create index if not exists ix_analytics_events_product_id  on analytics_events(product_id);
create index if not exists ix_analytics_events_event_type  on analytics_events(event_type);

-- ── orders ────────────────────────────────────────────────────────────────────
create table if not exists orders (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid not null references businesses(id) on delete cascade,
  product_id        uuid references products(id) on delete set null,
  stripe_session_id varchar(255) not null unique,
  customer_email    varchar(255),
  amount_cents      integer not null check (amount_cents >= 0),
  currency          varchar(3) not null default 'usd',
  status            varchar(60) not null default 'pending',
  raw_payload       jsonb not null default '{}'::jsonb,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists ix_orders_business_id       on orders(business_id);
create index if not exists ix_orders_product_id        on orders(product_id);
create index if not exists ix_orders_stripe_session_id on orders(stripe_session_id);

-- ── agent_logs ────────────────────────────────────────────────────────────────
create table if not exists agent_logs (
  id          uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  agent_type  varchar(80) not null,
  log_type    varchar(40) not null default 'decision',
  summary     varchar(500) not null,
  payload     jsonb not null default '{}'::jsonb,
  applied     boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists ix_agent_logs_business_id on agent_logs(business_id);
create index if not exists ix_agent_logs_agent_type  on agent_logs(agent_type);

-- ── agent_tasks ───────────────────────────────────────────────────────────────
create table if not exists agent_tasks (
  id            uuid primary key default gen_random_uuid(),
  business_id   uuid not null references businesses(id) on delete cascade,
  task_type     varchar(80) not null,
  status        varchar(40) not null default 'pending',
  payload       jsonb not null default '{}'::jsonb,
  result        jsonb not null default '{}'::jsonb,
  retries       integer not null default 0,
  error_message text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists ix_agent_tasks_business_id on agent_tasks(business_id);
create index if not exists ix_agent_tasks_status      on agent_tasks(status);
create index if not exists ix_agent_tasks_task_type   on agent_tasks(task_type);

-- ── experiments ───────────────────────────────────────────────────────────────
create table if not exists experiments (
  id          uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  name        varchar(160) not null,
  description text,
  status      varchar(40) not null default 'running',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists ix_experiments_business_id on experiments(business_id);
create index if not exists ix_experiments_status      on experiments(status);

-- ── landing_variants ──────────────────────────────────────────────────────────
create table if not exists landing_variants (
  id            uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references experiments(id) on delete cascade,
  name          varchar(80) not null,
  overrides     jsonb not null default '{}'::jsonb,
  weight        integer not null default 50,
  visitors      integer not null default 0,
  conversions   integer not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists ix_landing_variants_experiment_id on landing_variants(experiment_id);

-- ── experiment_assignments ────────────────────────────────────────────────────
create table if not exists experiment_assignments (
  id            uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references experiments(id) on delete cascade,
  variant_id    uuid not null references landing_variants(id) on delete cascade,
  visitor_token varchar(255) not null,
  converted     boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists ix_experiment_assignments_experiment_id on experiment_assignments(experiment_id);
create index if not exists ix_experiment_assignments_variant_id    on experiment_assignments(variant_id);
create index if not exists ix_experiment_assignments_visitor_token on experiment_assignments(visitor_token);
