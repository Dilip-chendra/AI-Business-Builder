# Requirements Document

## Introduction

This document covers four areas of the marketing platform evolution:

1. **AI Marketing Operating System** — Transform the existing demo marketing module into a real autonomous marketing platform with live OAuth integrations (LinkedIn, Twitter/X, Facebook, Instagram, Google Ads, Meta Ads, SendGrid/Mailchimp, WordPress), a full campaign lifecycle, AI image generation, real analytics attribution, a content calendar, and a redesigned "Mission Control" UI.
2. **AI Studio Bug Fixes** — Correct three broken API calls in the AI Studio page: wrong base URL for business listing, wrong preview iframe URL, and missing JWT Bearer token on all fetch calls.
3. **AI Code Editor — Project Switching** — Add a business/project selector to the code editor so workspace files are namespaced per business, with a "New File" button and backend support for `business_id`-scoped file paths.
4. **Browser Agent — Google First** — Change the search engine priority order so Google is tried first, followed by Bing, Yahoo, and DuckDuckGo.

The platform is built on FastAPI (backend), Next.js 14 (frontend), SQLite (dev DB), Groq/HF/Ollama AI, JWT authentication, SSE streaming, and inline styles (no Tailwind in new components).

---

## Glossary

- **Marketing_OS**: The AI Marketing Operating System — the upgraded marketing module that orchestrates real platform integrations, campaign lifecycle, and AI agents.
- **OAuth_Manager**: The backend service responsible for storing, refreshing, and revoking OAuth tokens for all third-party platform integrations.
- **Campaign**: A unit of marketing work with a defined type, content, targeting, lifecycle state, and metrics.
- **Campaign_Lifecycle**: The ordered set of states a Campaign passes through: `draft → pending_approval → scheduled → running → paused → completed → failed`.
- **Content_Calendar**: A chronological view of all scheduled Campaign posts grouped by date.
- **Brand_System**: The per-business configuration of colors, typography, tone of voice, target audience, industry, competitors, website URL, and logo used by AI agents during content generation.
- **AI_Agent**: A streaming, goal-directed AI worker (StrategyAgent, CopywritingAgent, SEOAgent, CreativeAgent, AnalyticsAgent, OptimizationAgent, TrendAgent).
- **Image_Pipeline**: The backend service that calls OpenAI DALL-E 3 (primary) or Stability AI (fallback) to generate campaign images and stores them in the uploads directory.
- **Content_Studio**: The UI section where users generate and manage individual content pieces (posts, threads, captions, emails, blogs, ad copy).
- **Mission_Control**: The redesigned marketing UI layout with left/centre/right panels and six tabs.
- **AI_Studio**: The existing page at `/ai-studio` that lets users modify their business landing page via AI prompts and preview the result.
- **Code_Editor**: The existing page at `/code-editor` that provides an AI-assisted code editing workspace.
- **Browser_Agent**: The autonomous web research agent in `backend/app/agents/browser_agent.py` that uses Playwright to search the web and extract information.
- **Workspace**: The directory on disk that holds code files for the Code_Editor, namespaced as `workspace/{business_id}/` when a business is selected.
- **JWT_Token**: The JSON Web Token stored in `localStorage` under the key `access_token`, used as a Bearer token in all authenticated API calls.
- **SSE**: Server-Sent Events — the streaming transport used by the marketing engine and AI agents.
- **ROAS**: Return on Ad Spend — a campaign performance metric.
- **CTR**: Click-Through Rate — clicks divided by impressions, expressed as a percentage.
- **CPC**: Cost Per Click — the average cost paid per ad click.

---

## Requirements

### Requirement 1: OAuth Platform Integration Management

**User Story:** As a business owner, I want to connect my social and advertising accounts via OAuth, so that the Marketing_OS can publish content and launch campaigns on my behalf without me manually copying credentials.

#### Acceptance Criteria

1. THE OAuth_Manager SHALL support OAuth 2.0 connect flows for the following platforms: LinkedIn, Twitter/X, Facebook, Instagram, Google Ads, Meta Ads, SendGrid, Mailchimp, and WordPress.
2. WHEN a user initiates an OAuth connect flow for a platform, THE OAuth_Manager SHALL redirect the user to the platform's authorization URL and handle the callback to exchange the authorization code for access and refresh tokens.
3. WHEN an OAuth access token is within 5 minutes of expiry, THE OAuth_Manager SHALL automatically refresh it using the stored refresh token before any API call is made.
4. THE OAuth_Manager SHALL store all OAuth tokens encrypted at rest in the database using AES-256 encryption.
5. WHEN an OAuth token refresh fails, THE OAuth_Manager SHALL mark the integration as `disconnected` and notify the user via a UI status indicator.
6. THE Marketing_OS SHALL display a connection status badge (connected / disconnected / expired) for each platform on the Integrations tab.
7. WHEN a user clicks "Disconnect" for a connected platform, THE OAuth_Manager SHALL revoke the token with the platform API and delete the stored credentials from the database.
8. WHEN a user clicks "Reconnect" for a disconnected platform, THE OAuth_Manager SHALL restart the OAuth connect flow for that platform.
9. IF a platform API call fails with a 401 or 403 response, THEN THE OAuth_Manager SHALL attempt one token refresh and retry the call before surfacing an error to the user.
10. THE OAuth_Manager SHALL support account selection after OAuth authorization, allowing the user to choose which page, ad account, or profile to use when a platform exposes multiple accounts.

---

### Requirement 2: Real Campaign Publishing

**User Story:** As a marketer, I want to publish AI-generated content directly to connected platforms with a single click, so that I do not have to copy-paste content between tools.

#### Acceptance Criteria

1. WHEN AI generates LinkedIn content for a Campaign, THE Marketing_OS SHALL display a "Post to LinkedIn" button that calls the LinkedIn API to publish the post to the user's selected company page or personal profile.
2. WHEN AI generates Instagram content for a Campaign, THE Marketing_OS SHALL display a "Publish to Instagram" button and a "Schedule Reel" button that call the Instagram Graph API.
3. WHEN AI generates a Google Ads Campaign payload and the Campaign status is `approved`, THE Marketing_OS SHALL display a "Launch Campaign" button that calls the Google Ads API to create the campaign, ad groups, and ads.
4. WHEN AI generates an email Campaign and the Campaign status is `approved`, THE Marketing_OS SHALL display a "Send Campaign" button that calls the configured SendGrid or Mailchimp API to deliver the email to the recipient list.
5. WHEN AI generates a blog post for a Campaign, THE Marketing_OS SHALL display a "Publish to WordPress" button that calls the WordPress REST API to create a new post.
6. WHEN a publish API call fails, THE Marketing_OS SHALL display the platform's error message to the user and set the Campaign status to `failed`.
7. WHEN a publish API call fails with a retryable error (HTTP 429 or 5xx), THE Marketing_OS SHALL retry the call up to 3 times with exponential back-off before setting the Campaign status to `failed`.
8. THE Marketing_OS SHALL update the Campaign status to `running` immediately after a successful publish API call for ad campaigns, and to `completed` for one-time posts and emails.

---

### Requirement 3: AI Image Generation Pipeline

**User Story:** As a marketer, I want the AI to automatically generate on-brand images for my campaigns, so that I do not need a separate design tool for basic ad creatives and social post images.

#### Acceptance Criteria

1. WHEN a Campaign requires an image (banner, ad creative, social post image, or thumbnail), THE Image_Pipeline SHALL call the OpenAI DALL-E 3 API to generate the image.
2. IF the DALL-E 3 API call fails or is unavailable, THEN THE Image_Pipeline SHALL fall back to the Stability AI API to generate the image.
3. WHEN generating an image, THE Image_Pipeline SHALL incorporate the business's Brand_System colors, logo description, and tone of voice into the generation prompt.
4. WHEN an image is successfully generated, THE Image_Pipeline SHALL store the image file in the `uploads/` directory and persist the file path in the Campaign record.
5. THE Image_Pipeline SHALL generate images in the following formats on request: campaign banner (1200×628 px), square social post (1080×1080 px), story/reel (1080×1920 px), and ad thumbnail (300×250 px).
6. WHEN an image is generated, THE Marketing_OS SHALL display it in the Campaign content card with an "Regenerate" button that triggers a new Image_Pipeline call.

---

### Requirement 4: Campaign Lifecycle Management

**User Story:** As a marketer, I want campaigns to move through a defined lifecycle with scheduling and timezone support, so that I can plan content in advance and track what is running versus what is completed.

#### Acceptance Criteria

1. THE Marketing_OS SHALL enforce the following Campaign_Lifecycle state machine: `draft → pending_approval → scheduled → running → paused → completed → failed`.
2. WHEN a Campaign is in `scheduled` state, THE Marketing_OS SHALL publish it at the user-specified date and time, converted to UTC using the user's selected timezone.
3. THE Marketing_OS SHALL display a Content_Calendar view that lists all `scheduled` and `running` Campaigns grouped by date in chronological order.
4. WHEN a user clicks "Duplicate Campaign", THE Marketing_OS SHALL create a new Campaign in `draft` state with the same content, targeting, and platform as the original.
5. THE Marketing_OS SHALL support A/B testing by allowing a Campaign to have two content variants (Variant A and Variant B), each tracked independently for impressions, clicks, and conversions.
6. WHEN an A/B test Campaign is `running`, THE Marketing_OS SHALL display the performance metrics for both variants side by side and indicate which variant is performing better.
7. WHEN a user clicks "Pause" on a `running` Campaign, THE Marketing_OS SHALL call the relevant platform API to pause the campaign and set the Campaign status to `paused`.
8. WHEN a user clicks "Resume" on a `paused` Campaign, THE Marketing_OS SHALL call the relevant platform API to resume the campaign and set the Campaign status to `running`.

---

### Requirement 5: Specialized AI Agents

**User Story:** As a marketer, I want specialized AI agents to handle distinct parts of campaign creation — strategy, copywriting, SEO, creative, analytics, optimization, and trend detection — so that each task is handled by a focused expert rather than a single generic model.

#### Acceptance Criteria

1. THE Marketing_OS SHALL provide a StrategyAgent that, given a campaign goal and budget, generates a structured campaign strategy including recommended platforms, content types, posting schedule, and KPI targets, streamed via SSE.
2. THE Marketing_OS SHALL provide a CopywritingAgent that generates platform-specific ad copy, social posts, and email sequences based on the campaign strategy and Brand_System, streamed via SSE.
3. THE Marketing_OS SHALL provide an SEOAgent that generates blog posts, meta descriptions, and keyword lists optimized for the target keyword, streamed via SSE.
4. THE Marketing_OS SHALL provide a CreativeAgent that constructs image generation prompts incorporating Brand_System attributes and calls the Image_Pipeline to produce campaign images, streamed via SSE.
5. THE Marketing_OS SHALL provide an AnalyticsAgent that reads Campaign metrics from the database and generates a natural-language performance report with anomaly detection, streamed via SSE.
6. THE Marketing_OS SHALL provide an OptimizationAgent that analyzes underperforming Campaigns (CTR below 1% or ROAS below 1.0) and suggests specific headline, CTA, and targeting improvements, streamed via SSE.
7. THE Marketing_OS SHALL provide a TrendAgent that queries the Browser_Agent for trending hashtags and topics relevant to the business's niche and returns a ranked list, streamed via SSE.
8. WHEN any AI_Agent stream produces an error event, THE Marketing_OS SHALL display the error message in the agent activity log and allow the user to retry the agent.

---

### Requirement 6: Real Analytics and Attribution

**User Story:** As a marketer, I want to see real performance metrics for my campaigns with AI-generated insights, so that I can make data-driven decisions about where to invest my marketing budget.

#### Acceptance Criteria

1. THE Marketing_OS SHALL track the following metrics per Campaign: impressions, clicks, CTR, CPC, conversions, ROAS, and engagement rate.
2. THE Marketing_OS SHALL display a line chart showing metric trends over time for each Campaign on the Analytics tab.
3. THE Marketing_OS SHALL display a bar chart comparing performance across all active Campaigns on the Analytics tab.
4. WHEN the AnalyticsAgent detects that a Campaign's CTR has dropped more than 20% compared to its 7-day average, THE Marketing_OS SHALL surface an anomaly alert in the Analytics tab.
5. THE Marketing_OS SHALL attribute conversions to the Campaign that last touched the user before the conversion event, using a last-touch attribution model.
6. WHEN a user views the Analytics tab, THE Marketing_OS SHALL display an AI insights panel generated by the AnalyticsAgent summarizing top-performing campaigns, underperformers, and recommended next actions.

---

### Requirement 7: Mission Control UI Redesign

**User Story:** As a marketer, I want a purpose-built "Mission Control" interface for the marketing module, so that I can see campaign execution, agent activity, and generated content all in one place without switching between separate tools.

#### Acceptance Criteria

1. THE Marketing_OS SHALL render a three-panel layout: a left panel for campaign goal input, platform selector, and agent activity log; a centre panel for live campaign execution view showing agent steps, generation progress, and publishing status; and a right panel for generated content cards.
2. THE Marketing_OS SHALL provide six navigation tabs: Engine, Campaigns, Content Studio, Analytics, Integrations, and Calendar.
3. WHEN the Engine tab is active, THE Marketing_OS SHALL display the agent activity log in the left panel, streaming each agent's step events in real time via SSE.
4. WHEN a content card is displayed in the right panel, THE Marketing_OS SHALL show: a platform preview of the post, an estimated engagement score, hashtag suggestions, the recommended best posting time, and AI optimization suggestions.
5. THE Marketing_OS SHALL use inline styles exclusively for all new UI components (no Tailwind CSS classes).
6. WHEN the Integrations tab is active, THE Marketing_OS SHALL display a card for each supported platform showing its connection status, connected account name, and Connect/Disconnect buttons.
7. WHEN the Calendar tab is active, THE Marketing_OS SHALL display the Content_Calendar view with scheduled posts grouped by date.

---

### Requirement 8: Content Studio

**User Story:** As a marketer, I want a dedicated Content Studio where I can generate any type of marketing content with tone, audience, and CTA controls, so that I can produce on-brand content for any channel without leaving the platform.

#### Acceptance Criteria

1. THE Content_Studio SHALL support generation of the following content types: LinkedIn posts, Twitter/X threads, Instagram captions, carousel scripts, YouTube descriptions, email sequences, landing page copy, ad copy, and blog posts.
2. THE Content_Studio SHALL provide a tone selector with at least the following options: Professional, Casual, Humorous, Inspirational, and Urgent.
3. THE Content_Studio SHALL provide an audience selector that is pre-populated from the business's Brand_System target audience definition.
4. THE Content_Studio SHALL provide a CTA selector with at least the following options: Learn More, Buy Now, Sign Up, Book a Demo, and Download.
5. WHEN content is generated, THE Content_Studio SHALL apply platform-specific optimizations (character limits for Twitter/X, hashtag density for Instagram, professional framing for LinkedIn).
6. THE Content_Studio SHALL use the AI memory stored for the business (brand voice, tone, audience) automatically during all content generation without requiring the user to re-enter brand details.

---

### Requirement 9: Brand System

**User Story:** As a business owner, I want to define my brand identity once and have the AI use it automatically across all marketing content, so that every generated post, ad, and email is consistent with my brand.

#### Acceptance Criteria

1. THE Brand_System SHALL allow users to define the following attributes per business: primary and secondary brand colors (hex codes), typography preferences, tone of voice, target audience description, industry, competitor names, website URL, and logo image.
2. WHEN any AI_Agent generates content, THE Brand_System SHALL inject the business's brand attributes into the AI prompt automatically.
3. WHEN the Image_Pipeline generates an image, THE Brand_System SHALL include the business's primary color and logo description in the DALL-E or Stability AI prompt.
4. THE Brand_System SHALL persist brand attributes in the database and make them available to all AI_Agents without requiring the user to re-enter them per session.
5. WHEN a user updates a Brand_System attribute, THE Marketing_OS SHALL use the updated value for all subsequent AI generation calls within the same session.

---

### Requirement 10: AI Studio Bug Fix — Business Selector

**User Story:** As a user of AI Studio, I want the business selector to load my businesses correctly, so that I can choose which business to edit without seeing "No businesses".

#### Acceptance Criteria

1. THE AI_Studio SHALL set `API_URL` to `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"` (including the `/api/v1` prefix).
2. WHEN the AI_Studio page loads, THE AI_Studio SHALL fetch the list of businesses from `${API_URL}/businesses` using the JWT_Token from `localStorage` as a Bearer token in the `Authorization` header, matching the authentication pattern used by all other pages.
3. THE AI_Studio SHALL NOT use `credentials: "include"` for the businesses fetch call; it SHALL use `Authorization: Bearer <token>` instead.
4. WHEN the businesses fetch returns an empty array or fails, THE AI_Studio SHALL display a "No businesses found" message in the selector rather than silently showing an empty dropdown.

---

### Requirement 11: AI Studio Bug Fix — Preview URL

**User Story:** As a user of AI Studio, I want the preview iframe to show my business's landing page, so that I can see the effect of AI changes in real time.

#### Acceptance Criteria

1. WHEN a business is selected in AI_Studio, THE AI_Studio SHALL set the preview iframe `src` to `${window.location.origin}/landing/${selectedBusiness}` (the Next.js landing page route), not to `${API_URL}/businesses/${selectedBusiness}/preview`.
2. WHEN the selected business changes, THE AI_Studio SHALL update the preview iframe `src` to reflect the newly selected business's landing page URL.

---

### Requirement 12: AI Studio Bug Fix — JWT Token on All Fetch Calls

**User Story:** As a user of AI Studio, I want all API calls to use my JWT token, so that the AI memory fetch and the playground modify call do not fail with 401 errors.

#### Acceptance Criteria

1. WHEN the AI_Studio fetches AI memory for a business, THE AI_Studio SHALL include the JWT_Token as a Bearer token in the `Authorization` header and SHALL NOT use `credentials: "include"`.
2. WHEN the AI_Studio sends a playground modify request to `${API_URL}/agent/playground/modify`, THE AI_Studio SHALL include the JWT_Token as a Bearer token in the `Authorization` header and SHALL NOT use `credentials: "include"`.

---

### Requirement 13: Code Editor — Business/Project Selector

**User Story:** As a developer, I want to switch between different business projects in the code editor, so that the workspace files I see and edit are relevant to the business I am working on.

#### Acceptance Criteria

1. THE Code_Editor SHALL display a business/project selector in the top bar that lists all businesses belonging to the authenticated user.
2. WHEN a user selects a business in the Code_Editor, THE Code_Editor SHALL reload the file list from `${API_URL}/code-editor/files?business_id={business_id}` and display the files for that business's Workspace.
3. THE Code_Editor backend endpoint `GET /code-editor/files` SHALL accept an optional `business_id` query parameter and serve files from `workspace/{business_id}/` when provided, falling back to `workspace/` when the parameter is absent.
4. THE Code_Editor backend endpoint `GET /code-editor/file` SHALL accept an optional `business_id` query parameter and read the file from `workspace/{business_id}/{path}` when provided.
5. THE Code_Editor backend endpoint `POST /code-editor/file` SHALL accept an optional `business_id` field in the request body and write the file to `workspace/{business_id}/{path}` when provided.
6. WHEN a business is selected and its Workspace directory does not yet exist, THE Code_Editor backend SHALL create the directory `workspace/{business_id}/` automatically before serving or writing files.

---

### Requirement 14: Code Editor — New File Button

**User Story:** As a developer, I want to create new files in the workspace directly from the code editor, so that I can start writing new components or scripts without leaving the editor.

#### Acceptance Criteria

1. THE Code_Editor SHALL display a "New File" button in the file tree panel.
2. WHEN a user clicks "New File", THE Code_Editor SHALL prompt the user for a filename and create an empty file at `workspace/{business_id}/{filename}` (or `workspace/{filename}` if no business is selected) via a `POST /code-editor/file` call.
3. WHEN the new file is created successfully, THE Code_Editor SHALL add it to the file list and open it in the editor automatically.
4. IF the filename provided by the user is empty or contains path traversal characters (`..` or leading `/`), THEN THE Code_Editor SHALL display a validation error and SHALL NOT create the file.

---

### Requirement 15: Browser Agent — Google-First Search Order

**User Story:** As a user of the browser agent, I want Google to be the primary search engine, so that research results are sourced from the most comprehensive index first.

#### Acceptance Criteria

1. THE Browser_Agent SHALL attempt search engines in the following priority order: Google, Bing, Yahoo, DuckDuckGo.
2. THE Browser_Agent SHALL use the Google search URL `https://www.google.com/search?q={encoded_query}&hl=en` as the first entry in the `search_urls` list inside `_browser_async`.
3. WHEN Google returns a blocked or empty response (title contains "access denied", "blocked", "captcha", "robot", "verify", "unusual traffic", or "error", or body text is under 200 characters), THE Browser_Agent SHALL fall through to Bing as the next search engine.
4. THE Browser_Agent SHALL preserve the existing fallback behavior: if all search engines are blocked, it SHALL answer from AI knowledge using `_ai_text_sync`.
