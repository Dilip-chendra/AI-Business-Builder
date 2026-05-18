# Autonomous Agent System

## Architecture

```
User Goal
    │
    ▼
AgentController / BrowserAgent
    │
    ├── Safety Layer (MANDATORY — every action passes through this)
    │   ├── PermissionService  — RBAC: agent < user < admin
    │   ├── ActionValidator    — schema + value + pattern checks
    │   └── CostTracker        — step/token/request/cost limits
    │
    ├── ToolExecutor (single gateway — no direct tool calls)
    │
    └── Tool Registry
        ├── Internal Tools     — get_business, create_product, get_analytics, ...
        └── Browser Tools      — open_url, click, extract_text, search_google, ...
```

## Safety Rules

Every action goes through this pipeline:

```
Permission Check → Action Validation → Duplicate Detection → Cost Check → Execute → Log
```

**Blocked always (regardless of role):**
- `submit_payment`, `buy`, `purchase`
- `delete_all`, `overwrite_all`
- `login`, `fill_password`

**Blocked for AGENT role:**
- `create_product`, `update_product`, `send_email`
- All write operations

**Blocked for USER role:**
- `delete_product`, `delete_business`, `bulk_update`

**Requires human confirmation:**
- `delete_product`, `delete_business`, `send_email`, `bulk_update`

## Limits (configurable in .env)

| Limit | Default | Env var |
|---|---|---|
| Max steps per run | 10 | `AGENT_MAX_STEPS` |
| Max AI requests per run | 20 | `AGENT_MAX_REQUESTS_PER_RUN` |
| Max tokens per run | 50,000 | `AGENT_MAX_TOKENS_PER_RUN` |
| Max cost per run | $0.50 | `AGENT_MAX_COST_USD` |

## API

```
POST /api/v1/agent/run          — General agent (internal tools)
POST /api/v1/agent/browser/run  — Browser research agent
GET  /api/v1/agent/status/{id}  — Run status
GET  /api/v1/agent/logs/{id}    — Full step logs
```

## Browser Agent

Requires Playwright:
```cmd
.venv\Scripts\playwright install chromium
```

The browser agent:
- Never logs into external sites
- Never submits payments
- Never accesses localhost or internal IPs
- Stops after 8 steps maximum
- Returns structured JSON with sources

## Example Goals

**Internal agent:**
- "Get analytics for my business and suggest improvements"
- "Create a new product called 'Premium Kit' priced at $99"
- "Update my business headline to be more compelling"

**Browser agent:**
- "Find top 3 competitors pricing for AI SaaS tools"
- "Research trending digital products in the productivity niche"
- "Find SEO keywords for fitness coaching businesses"
