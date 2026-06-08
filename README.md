# AI Business Builder

AI Business Builder is an AI-native SaaS platform for creating, operating, marketing, and improving digital businesses from one workspace. It combines business generation, AI Studio, a real project workspace, marketing automation, browser-assisted research, analytics, integrations, and deployment tooling into a single operating system.

The project is built as a full-stack application with a FastAPI backend, a Next.js frontend, SQLAlchemy/Alembic persistence, Playwright browser automation, OAuth integrations, and multi-provider AI routing.

## What This Platform Does

- Generate business profiles, landing pages, products, and go-to-market assets.
- Edit landing pages and project files through AI Studio and the AI Code Editor.
- Run internal AI agents for strategy, planning, SEO ideation, campaign generation, and business analysis.
- Run browser agents for live web research, evidence collection, source extraction, and browser-assisted publishing workflows.
- Generate, approve, schedule, and publish marketing campaigns using real integrations where configured.
- Track real analytics, campaign status, events, versions, and activity logs.
- Connect services such as Google/Gmail, Notion, SendGrid, LinkedIn, WordPress, and other providers through backend-managed integrations.

## Current Provider Strategy

Featherless support has been disabled in this codebase because trial access is being phased out. AI routing now prefers:

1. Groq
2. Ollama
3. Hugging Face

At least one working text provider is required for AI generation features. Ollama can be used as a local fallback when installed and running.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind-compatible styling, Framer Motion, Lucide icons |
| Backend | FastAPI, Python, SQLAlchemy async ORM, Alembic |
| Database | SQLite for local development, PostgreSQL-ready for production |
| AI Providers | Groq, Hugging Face, Ollama |
| Browser Automation | Playwright |
| Integrations | OAuth/API tool routes for Gmail/Google, Notion, SendGrid, LinkedIn, and other platforms |
| Background/Cache | Redis optional, in-memory fallback for local development |
| Deployment | Docker Compose, Nginx, production deployment guide |

## Repository Structure

```text
AI-Business-Builder/
  backend/
    app/
      api/routes/          FastAPI route modules
      core/                Configuration, auth, cache, security
      models/              SQLAlchemy models
      services/            AI, marketing, browser, integrations, business logic
    migrations/            Alembic migrations
    requirements.txt       Python dependencies

  frontend/
    app/                   Next.js App Router pages
    components/            Shared UI components
    lib/                   API client, types, context, utilities
    package.json           Frontend scripts and dependencies

  database/                Database-related project files
  docker/                  Docker/Nginx support files
  scripts/                 Utility scripts
  uploads/                 Local upload storage
  workspace/               Generated project workspaces
  start.py                 Full-stack launcher
  DEPLOYMENT.md            Production deployment guide
  SETUP.md                 Additional setup notes
```

## Prerequisites

| Requirement | Recommended Version |
|---|---|
| Python | 3.11 or newer |
| Node.js | 18 or newer |
| Git | Any modern version |
| Ollama | Optional, for local AI fallback |
| Redis | Optional, for production-like queue/cache behavior |

On Windows, run commands from PowerShell inside the repository root.

## Quick Start

Start the full stack with one command:

```powershell
python start.py
```

The launcher will:

1. Check Python and Node.js.
2. Prepare backend and frontend environment files.
3. Create or reuse the backend virtual environment.
4. Install backend and frontend dependencies when needed.
5. Install Playwright browser prerequisites when needed.
6. Run Alembic migrations.
7. Check or start Ollama when available.
8. Start the backend on `http://localhost:8000`.
9. Start the frontend on `http://localhost:3000`.
10. Write logs to `.runtime/logs`.

Useful launcher commands:

```powershell
python start.py --skip-install
python start.py --dev
python start.py --no-browser
python start.py --status
python start.py --stop
python start.py --backend-only
python start.py --frontend-only
```

For fast local development, this is usually enough:

```powershell
python start.py --skip-install --no-browser --dev
```

## Manual Development Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Local URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/api/docs |
| Backend health | http://localhost:8000/health |
| Backend readiness | http://localhost:8000/ready |
| AI health | http://localhost:8000/api/v1/ai/health |

## Environment Configuration

The backend reads secrets from `backend/.env`. Never place private keys in frontend files, browser storage, screenshots, source commits, or documentation.

Important backend variables:

```env
APP_ENV=development
DATABASE_URL=sqlite+aiosqlite:///./autonomous_builder.db
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

JWT_SECRET_KEY=change-me-in-production
ENCRYPTION_KEY=

GROQ_API_KEY=
GROQ_MODEL=llama3-8b-8192

HF_API_KEY=
HUGGINGFACE_API_KEY=
HF_MODEL=mistralai/Mistral-7B-Instruct-v0.2

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

IMAGE_PROVIDER=huggingface
HUGGINGFACE_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0

SENDGRID_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google/callback

NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
NOTION_REDIRECT_URI=http://localhost:8000/api/v1/integrations/notion/callback

LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/integrations/linkedin/callback
```

The frontend reads public configuration from `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_PAYPAL_CLIENT_ID=
```

Only values prefixed with `NEXT_PUBLIC_` are safe for the browser.

## AI Studio

AI Studio is the prompt-to-project workspace. It sends user prompts to the backend, loads the selected business/project context, routes the request through AI providers, applies structured changes, persists versions, invalidates preview cache, and refreshes the live landing page preview.

Expected flow:

```text
User prompt
  -> Studio backend route
  -> AI provider router
  -> structured operation plan
  -> database/project file mutation
  -> version snapshot
  -> preview refresh
  -> timeline update
```

If an AI provider returns malformed JSON, the backend uses guarded recovery paths for common visible edits such as color changes, CTA updates, section additions, and business pivots. The app should not mark an action as successful unless a real mutation was applied.

## AI Code Editor

The AI Code Editor works against real generated project files. It supports:

- Project file tree loading.
- File reads and writes.
- AI-assisted code edits.
- Diff and version history.
- Preview invalidation after successful edits.

If no project files exist for the selected business, the UI should show a clear setup state instead of sample files.

## Marketing Engine

The Marketing Engine is designed as a real campaign operating system, not a simulated dashboard.

Core workflow:

1. Select business and product context.
2. Enter a campaign goal.
3. Select target platforms.
4. Generate campaign strategy and platform assets with AI.
5. Persist campaigns and campaign assets in the backend.
6. Review and approve generated content.
7. Publish, send, schedule, export, or run browser-assisted workflows.
8. Track real publishing attempts, events, and analytics.

Production rules:

- Draft campaigns show zero performance until real events exist.
- Revenue must come from real payment/order data.
- Email sending must use SendGrid or Gmail OAuth when configured.
- OAuth/API publishing must only show success after provider confirmation.
- Browser publishing must not claim success when it only reaches a login page.
- Missing providers must show setup-required states with clear next steps.

## Browser Agent

The Browser Agent uses Playwright for web research and browser-assisted operations. It is used when live website evidence or browser interaction is required.

Typical use cases:

- Competitor research.
- SEO and keyword research from live pages.
- Pricing extraction.
- Browser-assisted publishing where official APIs are unavailable.
- Verification screenshots and action logs.

The browser agent should report states honestly, such as `needs_login`, `composer_not_found`, `awaiting_user_approval`, `published`, or `failed`.

Install browser support manually if needed:

```powershell
cd backend
.\.venv\Scripts\playwright install chromium
```

## Integrations

Integrations are backend-managed. Normal users should not enter OAuth client IDs or secrets in the frontend. App-owner credentials belong in `backend/.env`; users connect accounts through OAuth.

Supported or planned integration categories:

- Google/Gmail and Google Calendar
- Notion
- SendGrid
- LinkedIn
- Twitter/X
- Facebook/Instagram/Meta
- WordPress
- Slack
- Google Ads and Meta Ads draft workflows

Integration security requirements:

- Encrypt stored tokens and browser-vault credentials.
- Never expose access tokens or refresh tokens to the frontend.
- Validate OAuth state.
- Refresh expired tokens before provider calls.
- Show reconnect/setup-required states when credentials are missing or expired.

## Testing

Backend tests:

```powershell
.\.ci-venv-backend\Scripts\python.exe -m pytest backend/tests -q
```

Focused backend tests:

```powershell
.\.ci-venv-backend\Scripts\python.exe -m pytest backend/tests/test_ai_studio_service.py backend/tests/test_studio_projects.py -q
.\.ci-venv-backend\Scripts\python.exe -m pytest backend/tests/test_marketing_routes.py -q
```

Frontend typecheck:

```powershell
cd frontend
npx tsc --noEmit --pretty false
```

Frontend build:

```powershell
cd frontend
npm run build
```

Quick route smoke checks after starting the app:

```powershell
Invoke-WebRequest http://localhost:3000/ai-studio -UseBasicParsing
Invoke-WebRequest http://localhost:3000/marketing -UseBasicParsing
Invoke-WebRequest http://localhost:8000/api/v1/ai/health -UseBasicParsing
```

## Troubleshooting

### Backend does not start

- Run `python start.py --status` to inspect process and port ownership.
- Check `.runtime/logs/backend.log`.
- Confirm `backend/.env` exists.
- Run migrations manually with `.\.ci-venv-backend\Scripts\python.exe -m alembic upgrade head` or through the launcher.
- Make sure port `8000` is not already occupied by another app.

### Frontend does not start

- Check `.runtime/logs/frontend.log`.
- Run `cd frontend && npm install`.
- Delete `frontend/.next` and restart if the Next.js cache is stale.
- Make sure port `3000` is free.

### AI provider is unavailable

- Check `http://localhost:8000/api/v1/ai/health`.
- Add a valid `GROQ_API_KEY`, `HF_API_KEY` or `HUGGINGFACE_API_KEY`.
- For local fallback, install Ollama and run:

```powershell
ollama pull llama3
```

### Image generation fails

- Confirm `IMAGE_PROVIDER=huggingface`.
- Set `HUGGINGFACE_API_KEY` or `HF_API_KEY`.
- Set `HUGGINGFACE_IMAGE_MODEL`, for example:

```env
HUGGINGFACE_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
```

- If you see DNS errors such as `getaddrinfo failed`, the backend cannot reach Hugging Face from the current network.

### SendGrid rejects email

- Verify the API key has mail-send permission.
- Verify the sender identity or sending domain in SendGrid.
- Check backend logs for the provider response. Do not log or expose the API key.

### Browser Agent stops at login

- This is expected if the platform requires login, CAPTCHA, 2FA, or manual verification.
- Save a browser-vault account only if you understand the security implications.
- Complete login manually in the live browser and retry/continue when the UI allows it.

## Deployment

For production, use the Docker-based deployment flow described in [DEPLOYMENT.md](DEPLOYMENT.md).

Production checklist:

- Use PostgreSQL instead of local SQLite.
- Set strong `JWT_SECRET_KEY` and `ENCRYPTION_KEY`.
- Configure `FRONTEND_URL`, `BACKEND_URL`, `CORS_ORIGINS`, and trusted hosts for your domain.
- Use secure cookies and HTTPS.
- Store secrets outside source control.
- Configure OAuth redirect URIs for the production backend URL.
- Use Redis for cache, queues, browser runs, and background workflows.
- Run migrations before serving traffic.
- Validate email sender identities before sending campaigns.

## Security Notes

- Treat any secret pasted into chat, screenshots, logs, or commits as compromised and rotate it.
- Do not put OAuth client secrets, API keys, passwords, or access tokens in frontend code.
- Do not return decrypted tokens to the browser.
- Do not show fake success states for integrations or publishing.
- Prefer official OAuth/API publishing. Use browser automation only as a fallback or explicit assisted mode.

## License

This repository includes a `LICENSE` file. Review it before distribution or commercial use.
