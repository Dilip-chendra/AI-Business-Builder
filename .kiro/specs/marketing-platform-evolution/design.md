# Design Document — Marketing Platform Evolution

## Overview

This document covers the technical design for four areas:

1. **AI Marketing Operating System** — Real OAuth integrations, campaign publishing, image generation, lifecycle management, specialized AI agents, analytics, Mission Control UI, Content Studio, Brand System.
2. **AI Studio Bug Fixes** — Fix API_URL prefix, preview iframe URL, and JWT token on all fetch calls.
3. **Code Editor Project Switching** — Business selector, namespaced workspaces, New File button.
4. **Browser Agent Google-First** — Change search engine priority order.

**Guiding principles:**
- Quick wins (Areas 2–4) are implemented first — they are 1–3 file changes each.
- Marketing OS (Area 1) is built incrementally: backend models → services → routes → frontend.
- No mock data, no fake API calls, no placeholder success states.
- All new frontend components use inline styles only.

---

## Architecture

### High-Level System Diagram

```
Frontend (Next.js 14)
  ├── /marketing          ← Mission Control UI (full redesign)
  ├── /ai-studio          ← Bug fixes (API_URL, preview, JWT)
  ├── /code-editor        ← Business selector + namespaced workspace
  └── /agent-live         ← Browser agent (Google-first)

Backend (FastAPI)
  ├── /marketing/*        ← Extended with publish, schedule, image gen
  ├── /integrations/*     ← NEW: OAuth connect/callback/status
  ├── /brand/*            ← NEW: Brand system CRUD
  ├── /code-editor/*      ← Extended with business_id param
  └── /agents/browser     ← Google-first search order

New Services
  ├── OAuthManagerService     ← Token storage, refresh, revocation
  ├── PublishingService       ← Platform-specific publish calls
  ├── ImageGenerationService  ← DALL-E 3 + Stability AI fallback
  ├── BrandSystemService      ← Brand context CRUD
  └── CampaignScheduler       ← Background job for scheduled posts
```

---

## Quick Wins (Areas 2–4) — Implement First

### Area 2: AI Studio Bug Fixes

**File:** `frontend/app/ai-studio/page.tsx`

Three targeted changes:

**Fix 1 — API_URL:**
```typescript
// BEFORE (wrong — missing /api/v1)
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// AFTER (correct)
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
```

**Fix 2 — Businesses fetch (JWT token, not credentials: include):**
```typescript
// BEFORE
fetch(`${API_URL}/businesses`, { credentials: "include" })

// AFTER
const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
fetch(`${API_URL}/businesses`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

**Fix 3 — Preview URL:**
```typescript
// BEFORE (wrong — this endpoint doesn't exist)
setPreviewUrl(`${API_URL}/businesses/${selectedBusiness}/preview`);

// AFTER (correct — uses the Next.js landing page route)
setPreviewUrl(`${typeof window !== "undefined" ? window.location.origin : "http://localhost:3000"}/landing/${selectedBusiness}`);
```

**Fix 4 — AI memory fetch (JWT token):**
```typescript
// BEFORE
fetch(`${API_URL}/ai/memory/${selectedBusiness}`, { credentials: "include" })

// AFTER
fetch(`${API_URL}/ai/memory/${selectedBusiness}`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

**Fix 5 — Playground modify call (JWT token):**
```typescript
// BEFORE
fetch(`${API_URL}/agent/playground/modify`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  credentials: "include",
  body: ...
})

// AFTER
fetch(`${API_URL}/agent/playground/modify`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: ...
})
```

---

### Area 3: Code Editor — Business Selector + Namespaced Workspace

**Frontend changes — `frontend/app/code-editor/page.tsx`:**
- Add `businesses` state and `selectedBusinessId` state
- Add business selector `<select>` in the top bar next to the title
- On business change: call `loadFiles(businessId)` with the new ID
- Pass `business_id` as query param to all file API calls

**Backend changes — `backend/app/api/routes/code_editor.py`:**

```python
# GET /code-editor/files?business_id=xxx
@router.get("/files")
async def list_files(
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    workspace = _get_workspace(business_id)
    workspace.mkdir(parents=True, exist_ok=True)
    # ... rest of listing logic using workspace path

def _get_workspace(business_id: str | None) -> Path:
    if business_id:
        ws = Path(f"workspace/{business_id}")
    else:
        ws = Path("workspace")
    ws.mkdir(parents=True, exist_ok=True)
    return ws
```

- `GET /code-editor/file?path=...&business_id=xxx` — reads from namespaced path
- `POST /code-editor/file` — body includes optional `business_id`, writes to namespaced path
- `POST /code-editor/new-file` — creates empty file, returns file info
- Seed workspace per business with starter files on first access

**New endpoint — `POST /code-editor/new-file`:**
```python
class NewFileRequest(BaseModel):
    path: str  # filename only, no path traversal
    business_id: str | None = None

@router.post("/new-file")
async def create_new_file(payload: NewFileRequest, ...) -> dict:
    # Validate: no ".." or leading "/"
    # Create empty file in workspace/{business_id}/{path}
    # Return file info
```

---

### Area 4: Browser Agent — Google First

**File:** `backend/app/agents/browser_agent.py`

Single change in `_browser_async`, the `search_urls` list:

```python
# BEFORE
search_urls = [
    f"https://www.bing.com/search?q={encoded}&form=QBLH",
    f"https://www.google.com/search?q={encoded}&hl=en",
    f"https://search.yahoo.com/search?p={encoded}",
    f"https://duckduckgo.com/?q={encoded}&ia=web",
]

# AFTER
search_urls = [
    f"https://www.google.com/search?q={encoded}&hl=en",
    f"https://www.bing.com/search?q={encoded}&form=QBLH",
    f"https://search.yahoo.com/search?p={encoded}",
    f"https://duckduckgo.com/?q={encoded}&ia=web",
]
```

---

## Area 1: AI Marketing Operating System

### New Data Models

```python
# backend/app/models/oauth_token.py
class OAuthToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "oauth_tokens"
    user_id: Mapped[str]          # FK → users.id
    business_id: Mapped[str]      # FK → businesses.id
    platform: Mapped[str]         # "linkedin"|"twitter"|"facebook"|"instagram"|"google_ads"|"meta_ads"|"sendgrid"|"mailchimp"|"wordpress"
    access_token_enc: Mapped[str] # AES-256 encrypted
    refresh_token_enc: Mapped[str | None]
    expires_at: Mapped[str | None] # ISO datetime
    account_id: Mapped[str | None] # selected account/page ID
    account_name: Mapped[str | None]
    status: Mapped[str]           # "connected"|"disconnected"|"expired"
    scopes: Mapped[str]           # JSON array of granted scopes

# backend/app/models/brand_system.py
class BrandSystem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "brand_systems"
    business_id: Mapped[str]      # FK → businesses.id, unique
    primary_color: Mapped[str]    # hex e.g. "#6366f1"
    secondary_color: Mapped[str]
    tone_of_voice: Mapped[str]    # "professional"|"casual"|"humorous"|"inspirational"|"urgent"
    target_audience: Mapped[str]
    industry: Mapped[str]
    competitors: Mapped[str]      # JSON array
    website_url: Mapped[str | None]
    logo_description: Mapped[str | None]  # text description for image gen
    extra: Mapped[str]            # JSON for additional fields

# backend/app/models/scheduled_post.py
class ScheduledPost(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_posts"
    campaign_id: Mapped[str]      # FK → marketing_campaigns.id
    business_id: Mapped[str]      # FK → businesses.id
    platform: Mapped[str]
    content_json: Mapped[str]     # JSON serialized post content
    scheduled_at_utc: Mapped[str] # ISO datetime UTC
    timezone: Mapped[str]         # e.g. "America/New_York"
    status: Mapped[str]           # "pending"|"published"|"failed"
    published_at: Mapped[str | None]
    error_message: Mapped[str | None]

# backend/app/models/campaign_metric.py
class CampaignMetric(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaign_metrics"
    campaign_id: Mapped[str]      # FK → marketing_campaigns.id
    recorded_at: Mapped[str]      # ISO datetime
    impressions: Mapped[int]
    clicks: Mapped[int]
    conversions: Mapped[int]
    spend_cents: Mapped[int]
    engagement: Mapped[int]
    platform: Mapped[str]
```

**Extended MarketingCampaign fields (migration):**
```python
# New columns added to marketing_campaigns:
scheduled_at: str | None          # ISO datetime for scheduled publishing
lifecycle_status: str             # full lifecycle state
image_url: str | None             # generated image path
variant_b_content: dict | None    # A/B test variant B
ab_test_active: bool
```

### New Services

**`OAuthManagerService`** — `backend/app/services/oauth_manager_service.py`
```python
class OAuthManagerService:
    async def get_token(self, user_id, business_id, platform) -> OAuthToken | None
    async def save_token(self, user_id, business_id, platform, access_token, refresh_token, expires_at, account_id, account_name, scopes) -> OAuthToken
    async def refresh_if_needed(self, token: OAuthToken) -> OAuthToken
    async def revoke(self, token: OAuthToken) -> None
    def encrypt(self, value: str) -> str   # AES-256 via cryptography lib
    def decrypt(self, value: str) -> str
```

**`PublishingService`** — `backend/app/services/publishing_service.py`
```python
class PublishingService:
    async def publish_linkedin_post(self, token: OAuthToken, content: dict) -> dict
    async def publish_twitter_post(self, token: OAuthToken, content: dict) -> dict
    async def publish_facebook_post(self, token: OAuthToken, content: dict) -> dict
    async def publish_instagram_post(self, token: OAuthToken, content: dict) -> dict
    async def launch_google_ads_campaign(self, token: OAuthToken, campaign: dict) -> dict
    async def send_sendgrid_email(self, token: OAuthToken, campaign: dict, recipients: list) -> dict
    async def publish_wordpress_post(self, token: OAuthToken, content: dict) -> dict
```

**`ImageGenerationService`** — `backend/app/services/image_generation_service.py`
```python
class ImageGenerationService:
    async def generate(self, prompt: str, size: str = "1024x1024", brand: BrandSystem | None = None) -> str
    # Returns local file path of saved image
    # Primary: OpenAI DALL-E 3 via /v1/images/generations
    # Fallback: Stability AI via /v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image
    def _build_brand_prompt(self, base_prompt: str, brand: BrandSystem) -> str
```

**`BrandSystemService`** — `backend/app/services/brand_system_service.py`
```python
class BrandSystemService:
    async def get(self, business_id: str) -> BrandSystem | None
    async def upsert(self, business_id: str, data: dict) -> BrandSystem
    def inject_into_prompt(self, prompt: str, brand: BrandSystem) -> str
```

### New API Routes

**`backend/app/api/routes/integrations.py`**
```
GET  /integrations/{business_id}                    — list all platform statuses
GET  /integrations/{business_id}/{platform}/connect — initiate OAuth flow (redirect)
GET  /integrations/{business_id}/{platform}/callback — OAuth callback handler
POST /integrations/{business_id}/{platform}/disconnect — revoke and delete token
GET  /integrations/{business_id}/{platform}/accounts — list available accounts
POST /integrations/{business_id}/{platform}/select-account — set active account
```

**`backend/app/api/routes/brand.py`**
```
GET  /brand/{business_id}   — get brand system
POST /brand/{business_id}   — create/update brand system
```

**Extended marketing routes:**
```
POST /marketing/{business_id}/campaigns/{campaign_id}/publish/{platform}  — publish to platform
POST /marketing/{business_id}/campaigns/{campaign_id}/schedule            — schedule post
POST /marketing/{business_id}/campaigns/{campaign_id}/generate-image      — generate image
GET  /marketing/{business_id}/calendar                                     — scheduled posts calendar
GET  /marketing/{business_id}/analytics                                    — campaign analytics
POST /marketing/{business_id}/content-studio/generate                     — content studio generation
```

### Frontend Architecture — Mission Control UI

**File:** `frontend/app/marketing/page.tsx` (full redesign)

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Top bar: business selector | tab navigation                        │
├──────────────────┬──────────────────────────┬───────────────────────┤
│  LEFT (320px)    │  CENTRE (flex 1)         │  RIGHT (300px)        │
│  Goal input      │  Live execution view     │  Generated content    │
│  Platform chips  │  Agent activity log      │  cards with actions   │
│  Quick goals     │  Generation progress     │  (Edit/Publish/Sched) │
└──────────────────┴──────────────────────────┴───────────────────────┘
```

**Tabs:** Engine | Campaigns | Content Studio | Analytics | Integrations | Calendar

**Key state:**
```typescript
type MarketingState = {
  businessId: string;
  tab: "engine"|"campaigns"|"content-studio"|"analytics"|"integrations"|"calendar";
  integrations: Record<string, IntegrationStatus>;
  brandSystem: BrandSystem | null;
  scheduledPosts: ScheduledPost[];
  analyticsData: AnalyticsData | null;
};

type IntegrationStatus = {
  platform: string;
  status: "connected"|"disconnected"|"expired";
  account_name: string | null;
};
```

**Content card actions (per campaign type):**
- Email: [Preview] [Edit] [Approve] [Send Campaign]
- LinkedIn: [Preview] [Edit] [Post to LinkedIn] [Schedule]
- Instagram: [Preview] [Edit] [Publish to Instagram] [Schedule Reel]
- Google Ads: [Preview] [Edit] [Approve] [Launch Campaign]
- Blog: [Preview] [Edit] [Publish to WordPress]
- All: [Regenerate] [Duplicate] [Optimize with AI] [Generate Image]

### Migrations

| Migration | Description |
|---|---|
| `0014_oauth_tokens.py` | oauth_tokens table |
| `0015_brand_systems.py` | brand_systems table |
| `0016_scheduled_posts.py` | scheduled_posts table |
| `0017_campaign_metrics.py` | campaign_metrics table |
| `0018_marketing_campaigns_extended.py` | Add lifecycle_status, scheduled_at, image_url, ab_test fields to marketing_campaigns |

### New File Structure

```
backend/app/
  models/
    oauth_token.py          NEW
    brand_system.py         NEW
    scheduled_post.py       NEW
    campaign_metric.py      NEW
  services/
    oauth_manager_service.py    NEW
    publishing_service.py       NEW
    image_generation_service.py NEW
    brand_system_service.py     NEW
  api/routes/
    integrations.py         NEW
    brand.py                NEW

frontend/app/
  marketing/
    page.tsx                REDESIGN (Mission Control)
  ai-studio/
    page.tsx                BUG FIXES (3 fixes)
  code-editor/
    page.tsx                EXTEND (business selector + new file)
```

---

## Correctness Properties

### P1 — OAuth tokens are never stored in plaintext
`OAuthManagerService.save_token()` always calls `encrypt()` before persisting. `get_token()` always calls `decrypt()` before returning. No raw token value appears in logs.

### P2 — Campaign publish is idempotent for one-time posts
Publishing a Campaign that is already in `completed` or `running` state returns the existing status without making a duplicate API call.

### P3 — Image generation falls back deterministically
If DALL-E 3 returns a non-200 response, `ImageGenerationService.generate()` calls Stability AI exactly once. If both fail, it raises `ImageGenerationError` — it never returns a placeholder URL.

### P4 — Scheduled posts fire within 60 seconds of their scheduled time
The background scheduler checks for due posts every 30 seconds. A post scheduled for time T is published between T and T+60s.

### P5 — Business workspace isolation
Files in `workspace/{business_id_A}/` are never accessible via requests scoped to `business_id_B`. The `_get_workspace()` function resolves paths relative to the business-scoped directory and rejects path traversal.

### P6 — AI Studio preview always shows the correct business
When `selectedBusiness` changes, `previewUrl` is updated synchronously before the iframe re-renders. The iframe `key` prop is incremented to force a reload.

### P7 — Browser agent tries Google before Bing
The first entry in `search_urls` is always the Google URL. This is enforced by the list literal order in `_browser_async`.
