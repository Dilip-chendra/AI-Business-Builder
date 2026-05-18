# Implementation Tasks — Marketing Platform Evolution

## Task List

- [x] 1. Quick Win: Browser Agent — Google First
  - [x] 1.1 In `backend/app/agents/browser_agent.py`, reorder `search_urls` list so Google (`https://www.google.com/search?q={encoded}&hl=en`) is first, Bing second, Yahoo third, DuckDuckGo fourth

- [x] 2. Quick Win: AI Studio Bug Fixes
  - [x] 2.1 Fix `API_URL` constant in `frontend/app/ai-studio/page.tsx` to include `/api/v1` prefix: `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"`
  - [x] 2.2 Fix businesses fetch to use JWT Bearer token from localStorage instead of `credentials: "include"`
  - [x] 2.3 Fix preview URL to use `${window.location.origin}/landing/${selectedBusiness}` instead of `${API_URL}/businesses/${selectedBusiness}/preview`
  - [x] 2.4 Fix AI memory fetch to use JWT Bearer token instead of `credentials: "include"`
  - [x] 2.5 Fix playground/modify fetch to use JWT Bearer token instead of `credentials: "include"`

- [x] 3. Quick Win: Code Editor — Business Selector and Namespaced Workspace
  - [x] 3.1 Add `_get_workspace(business_id: str | None) -> Path` helper to `backend/app/api/routes/code_editor.py` that returns `Path("workspace/{business_id}")` when business_id is provided, else `Path("workspace")`
  - [x] 3.2 Update `GET /code-editor/files` to accept optional `business_id` query param and use namespaced workspace path
  - [x] 3.3 Update `GET /code-editor/file` to accept optional `business_id` query param and read from namespaced path
  - [x] 3.4 Update `POST /code-editor/file` to accept optional `business_id` in request body and write to namespaced path
  - [x] 3.5 Add `POST /code-editor/new-file` endpoint that creates an empty file, validates no path traversal, and returns file info
  - [x] 3.6 Add business selector `<select>` to code editor top bar in `frontend/app/code-editor/page.tsx` that fetches businesses on mount and reloads files when selection changes
  - [x] 3.7 Add "New File" button to file tree panel that prompts for filename and calls `POST /code-editor/new-file`
  - [x] 3.8 Pass `business_id` as query param to all file API calls (list, read, save, versions, revert) in the frontend

- [x] 4. New Data Models — OAuth and Brand
  - [x] 4.1 Create `backend/app/models/oauth_token.py` with OAuthToken model (user_id, business_id, platform, access_token_enc, refresh_token_enc, expires_at, account_id, account_name, status, scopes)
  - [x] 4.2 Create `backend/app/models/brand_system.py` with BrandSystem model (business_id unique, primary_color, secondary_color, tone_of_voice, target_audience, industry, competitors JSON, website_url, logo_description, extra JSON)
  - [x] 4.3 Create `backend/app/models/scheduled_post.py` with ScheduledPost model (campaign_id, business_id, platform, content_json, scheduled_at_utc, timezone, status, published_at, error_message)
  - [x] 4.4 Create `backend/app/models/campaign_metric.py` with CampaignMetric model (campaign_id, recorded_at, impressions, clicks, conversions, spend_cents, engagement, platform)
  - [x] 4.5 Register all four new models in `backend/app/db/base.py`

- [x] 5. Database Migrations
  - [x] 5.1 Create `backend/migrations/versions/0014_oauth_tokens.py` migration for oauth_tokens table
  - [x] 5.2 Create `backend/migrations/versions/0015_brand_systems.py` migration for brand_systems table
  - [x] 5.3 Create `backend/migrations/versions/0016_scheduled_posts.py` migration for scheduled_posts table
  - [x] 5.4 Create `backend/migrations/versions/0017_campaign_metrics.py` migration for campaign_metrics table
  - [x] 5.5 Create `backend/migrations/versions/0018_marketing_campaigns_extended.py` migration adding lifecycle_status, scheduled_at, image_url, ab_test_active, variant_b_content columns to marketing_campaigns

- [x] 6. OAuth Manager Service
  - [x] 6.1 Create `backend/app/services/oauth_manager_service.py` with OAuthManagerService class: get_token, save_token, refresh_if_needed, revoke, encrypt, decrypt methods
  - [x] 6.2 Use Fernet symmetric encryption (from `cryptography` library) for token encryption; derive key from `settings.jwt_secret_key`
  - [x] 6.3 Add `cryptography` to `backend/requirements.txt`

- [x] 7. Brand System Service and Routes
  - [x] 7.1 Create `backend/app/services/brand_system_service.py` with BrandSystemService: get, upsert, inject_into_prompt methods
  - [x] 7.2 Create `backend/app/api/routes/brand.py` with `GET /brand/{business_id}` and `POST /brand/{business_id}` endpoints
  - [x] 7.3 Register brand router in `backend/app/api/router.py`

- [x] 8. Image Generation Service
  - [x] 8.1 Create `backend/app/services/image_generation_service.py` with ImageGenerationService: generate method calling OpenAI DALL-E 3 (primary) with Stability AI fallback
  - [x] 8.2 DALL-E 3 call: `POST https://api.openai.com/v1/images/generations` with model=dall-e-3, size, prompt; read `OPENAI_API_KEY` from settings
  - [x] 8.3 Stability AI fallback: `POST https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image`; read `STABILITY_API_KEY` from settings
  - [x] 8.4 Save generated image to `uploads/generated/{uuid}.png` and return the relative path
  - [x] 8.5 Add `OPENAI_API_KEY` and `STABILITY_API_KEY` to `backend/.env.example` (not `.env` — user must add their own keys)
  - [x] 8.6 Add `POST /marketing/{business_id}/campaigns/{campaign_id}/generate-image` endpoint that calls ImageGenerationService and updates campaign.image_url

- [x] 9. Publishing Service
  - [x] 9.1 Create `backend/app/services/publishing_service.py` with PublishingService class
  - [x] 9.2 Implement `publish_linkedin_post`: POST to LinkedIn Share API v2 (`https://api.linkedin.com/v2/ugcPosts`) using OAuth token
  - [x] 9.3 Implement `publish_twitter_post`: POST to Twitter API v2 (`https://api.twitter.com/2/tweets`) using OAuth 2.0 Bearer token
  - [x] 9.4 Implement `publish_facebook_post`: POST to Facebook Graph API (`https://graph.facebook.com/v18.0/{page_id}/feed`) using page access token
  - [x] 9.5 Implement `publish_instagram_post`: POST to Instagram Graph API (`https://graph.facebook.com/v18.0/{ig_user_id}/media` then `/media_publish`) using access token
  - [x] 9.6 Implement `send_sendgrid_email`: POST to SendGrid API (`https://api.sendgrid.com/v3/mail/send`) using API key
  - [x] 9.7 Implement `publish_wordpress_post`: POST to WordPress REST API (`{site_url}/wp-json/wp/v2/posts`) using application password auth
  - [x] 9.8 Add retry logic: on HTTP 429 or 5xx, retry up to 3 times with exponential backoff (1s, 2s, 4s)
  - [x] 9.9 Add `POST /marketing/{business_id}/campaigns/{campaign_id}/publish/{platform}` endpoint that calls PublishingService and updates campaign status

- [x] 10. OAuth Integration Routes
  - [x] 10.1 Create `backend/app/api/routes/integrations.py` with integration management endpoints
  - [x] 10.2 Implement `GET /integrations/{business_id}` — returns list of all platforms with connection status
  - [x] 10.3 Implement `GET /integrations/{business_id}/{platform}/connect` — returns OAuth authorization URL for the platform
  - [x] 10.4 Implement `GET /integrations/{business_id}/{platform}/callback` — handles OAuth callback, exchanges code for tokens, saves via OAuthManagerService
  - [x] 10.5 Implement `POST /integrations/{business_id}/{platform}/disconnect` — revokes token and marks as disconnected
  - [x] 10.6 Register integrations router in `backend/app/api/router.py`

- [x] 11. Campaign Scheduling
  - [x] 11.1 Add `POST /marketing/{business_id}/campaigns/{campaign_id}/schedule` endpoint accepting `scheduled_at` (ISO datetime) and `timezone` string, creating a ScheduledPost record
  - [x] 11.2 Add `GET /marketing/{business_id}/calendar` endpoint returning all ScheduledPost records for the business ordered by scheduled_at_utc
  - [x] 11.3 Add background task in `backend/app/tasks.py` that checks for due ScheduledPosts every 30 seconds and calls PublishingService for each

- [x] 12. Campaign Analytics Endpoints
  - [x] 12.1 Add `GET /marketing/{business_id}/analytics` endpoint returning aggregated CampaignMetric data per campaign for the last 30 days
  - [x] 12.2 Add `POST /marketing/{business_id}/campaigns/{campaign_id}/metrics` endpoint for recording metric snapshots (called by platform webhooks or manual refresh)

- [x] 13. Marketing Page — Mission Control UI Redesign
  - [x] 13.1 Redesign `frontend/app/marketing/page.tsx` with three-panel layout (left 320px, centre flex-1, right 300px) and six tabs: Engine, Campaigns, Content Studio, Analytics, Integrations, Calendar
  - [x] 13.2 Engine tab: left panel has goal textarea + platform chips + quick goals; centre panel has live SSE agent log; right panel has generated content cards
  - [x] 13.3 Each content card shows: campaign type icon, name, status badge, and contextual action buttons (Post to LinkedIn / Publish to Instagram / Launch Campaign / Send Campaign / Publish to WordPress) based on campaign_type
  - [x] 13.4 Publish buttons call `POST /marketing/{business_id}/campaigns/{campaign_id}/publish/{platform}` and show real success/error feedback (no fake alerts)
  - [x] 13.5 Schedule button opens a datetime picker and calls `POST /marketing/{business_id}/campaigns/{campaign_id}/schedule`
  - [x] 13.6 Generate Image button calls `POST /marketing/{business_id}/campaigns/{campaign_id}/generate-image` and displays the result image in the card
  - [x] 13.7 Campaigns tab: list of all campaigns with full lifecycle status, metrics, and action buttons
  - [x] 13.8 Content Studio tab: content type selector (LinkedIn post, Twitter thread, Instagram caption, email sequence, blog post, ad copy), tone selector, audience selector, CTA selector, generate button calling existing AI endpoints
  - [x] 13.9 Analytics tab: campaign performance table with impressions, clicks, CTR, conversions columns; AI insights panel calling AnalyticsAgent
  - [x] 13.10 Integrations tab: platform cards (LinkedIn, Twitter, Facebook, Instagram, Google Ads, Meta Ads, SendGrid, WordPress) each showing connection status and Connect/Disconnect buttons
  - [x] 13.11 Calendar tab: list of scheduled posts grouped by date with platform icon, content preview, and scheduled time

- [x] 14. Brand System Frontend
  - [x] 14.1 Add Brand System section to the marketing page (accessible from a "Brand Settings" button in the top bar)
  - [x] 14.2 Brand settings panel: primary color picker, secondary color picker, tone of voice selector, target audience input, industry input, competitors input, website URL input, logo description textarea
  - [x] 14.3 On save, call `POST /brand/{business_id}` and show success toast
  - [x] 14.4 On marketing page load, fetch brand system via `GET /brand/{business_id}` and display brand name/tone in the hero section

- [x] 15. Update lib/api.ts with New Endpoints
  - [x] 15.1 Add `publishCampaign(businessId, campaignId, platform)` method
  - [x] 15.2 Add `scheduleCampaign(businessId, campaignId, scheduledAt, timezone)` method
  - [x] 15.3 Add `generateCampaignImage(businessId, campaignId)` method
  - [x] 15.4 Add `getIntegrations(businessId)` method
  - [x] 15.5 Add `connectIntegration(businessId, platform)` method (returns OAuth URL)
  - [x] 15.6 Add `disconnectIntegration(businessId, platform)` method
  - [x] 15.7 Add `getBrandSystem(businessId)` method
  - [x] 15.8 Add `saveBrandSystem(businessId, data)` method
  - [x] 15.9 Add `getCalendar(businessId)` method
  - [x] 15.10 Add `getAnalytics(businessId)` method
