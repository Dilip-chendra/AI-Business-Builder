<<<<<<< HEAD
# Autonomous Business Builder — AI-Native SaaS Platform

A production-grade, multi-agent AI SaaS platform that generates, launches, and autonomously optimises online businesses.

---

## ONE-COMMAND STARTUP

### Windows (recommended)

```bat
python start.py
```

Or double-click `start.bat`

### macOS / Linux

```bash
python3 start.py
```

### Options

```bash
python start.py --skip-install   # Skip npm/pip install (faster if already set up)
python start.py --no-browser     # Don't open browser automatically
python start.py --dev            # Run frontend/backend in development mode
python start.py --status         # Show live service status
python start.py --stop           # Stop backend/frontend started by the launcher
python start.py --backend-only   # Start only the backend API
python start.py --frontend-only  # Start only the frontend
```

### What the launcher does automatically

1. Checks Python 3.11+ and Node.js 18+ are installed
2. Creates Python virtual environment (`backend/.venv`) if missing
3. Installs all backend Python dependencies (`pip install -r requirements.txt`)
4. Installs all frontend Node dependencies (`npm install`)
5. Checks `backend/.env` exists (copies from `.env.example` if missing)
6. Runs all database migrations (`alembic upgrade head`)
7. Installs Chromium for the Playwright browser agent
8. Starts the backend API server on **http://localhost:8000**
9. Builds and starts the frontend on **http://localhost:3000**
10. Waits for both to be ready, writes logs under `.runtime/logs`, then opens the app in your browser

---

## MANUAL STARTUP (if needed)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt        # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Mac/Linux
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## PREREQUISITES

| Requirement | Version | Download |
|---|---|---|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| Git | Any | https://git-scm.com |

**Optional (for full features):**
- Ollama (local AI): https://ollama.ai — run `ollama pull llama3` after install
- Playwright (browser agent): `backend\.venv\Scripts\playwright install chromium`

---

## CONFIGURATION

Edit `backend/.env` to configure:

```env
# AI Providers (at least one required)
GROQ_API_KEY=your_groq_key_here          # Free at console.groq.com
HF_API_KEY=your_huggingface_key_here     # Free at huggingface.co
OLLAMA_BASE_URL=http://localhost:11434   # Local Ollama

# Image Generation (optional)
OPENAI_API_KEY=                          # For DALL-E 3 image generation
STABILITY_API_KEY=                       # Stability AI fallback

# Platform Integrations (optional — for real publishing)
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
SENDGRID_API_KEY=                        # For real email sending
```

---

## URLS WHEN RUNNING

| Service | URL |
|---|---|
| App | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/api/docs |
| Health Check | http://localhost:8000/health |
| Readiness Check | http://localhost:8000/ready |

---

## ARCHITECTURE

```
Autonomous Business Builder
├── backend/                    FastAPI Python backend
│   ├── app/
│   │   ├── models/             SQLAlchemy ORM models
│   │   ├── services/           Business logic + AI services
│   │   ├── api/routes/         REST API endpoints
│   │   ├── agents/             AI agent implementations
│   │   └── core/               Config, security, logging
│   └── migrations/             Alembic database migrations
│
└── frontend/                   Next.js 14 frontend
    ├── app/                    App Router pages
    ├── components/             Shared React components
    ├── hooks/                  Custom React hooks
    └── lib/                    API client, types, auth
```

### Key Features

- **AI Business Generation** — Describe an idea, AI builds a complete business with landing page, products, and marketing strategy
- **Mission Control Marketing** — Real publishing to LinkedIn, Twitter, Facebook, Instagram, WordPress via OAuth APIs
- **AI Code Editor** — Multi-file editor with Cmd+K inline AI, RAG codebase search, agent plan panel
- **Agent Live** — Real-time autonomous agent with browser research capability
- **AI Ops Panel** — Provider health monitoring, circuit breaker, latency charts, live SSE events
- **Workspace System** — Multi-project architecture with team collaboration
- **Deployment System** — Preview and production deploys with AI pre-deploy checks

---

## FIRST TIME SETUP

1. Clone the repository
2. Run `python start.py` (or `python3 start.py` on Mac/Linux)
3. Sign up at http://localhost:3000/signup
4. Click "Generate my first business" on the dashboard
5. Explore the Marketing, Analytics, and Agent Live pages

---

## TROUBLESHOOTING

**Backend won't start:**
- Check `backend/.env` has valid `GROQ_API_KEY` or `HF_API_KEY`
- Run `cd backend && .venv\Scripts\alembic upgrade head` manually
- Check port 8000 is not in use

**Frontend won't start:**
- Run `cd frontend && npm install` manually
- Check port 3000 is not in use
- Delete `frontend/.next` and retry

**"No AI providers available":**
- Add `GROQ_API_KEY` to `backend/.env` (free at https://console.groq.com)
- Or install Ollama and run `ollama pull llama3`

**Browser agent not working:**
- Run: `backend\.venv\Scripts\playwright install chromium`

---

## PRODUCTION DEPLOYMENT

The repo now includes a production Docker stack with:

- Next.js frontend container
- FastAPI + Gunicorn backend container
- dedicated Playwright browser-agent worker
- Redis
- PostgreSQL
- Ollama
- Nginx reverse proxy
- optional Prometheus + Grafana

Start with the full guide in [DEPLOYMENT.md](DEPLOYMENT.md).

## CLOSEST FREE CLOUD DEPLOY

If you need the closest always-online free evaluation path, use Render’s free tier with the repo blueprint:

- guide: [DEPLOY_FREE.md](DEPLOY_FREE.md)
- blueprint: [render.yaml](render.yaml)
- one-click import: [Deploy to Render](https://render.com/deploy?repo=https://github.com/Dilip-chendra/Autonomous-Business-Builder.git)

This path is suitable for demos and evaluation, but Render’s own docs say free instances are **not for production** and may sleep or restart:
[Render free docs](https://render.com/docs/free)
=======
# AI-Business-Builder
AI Business Builder is an autonomous AI-powered business operating system that combines AI workflows, browser agents, marketing automation, AI code editing, analytics, and business generation into one platform. Built using Next.js, FastAPI, Playwright, Ollama, Groq, and multi-model AI orchestration.
>>>>>>> parent of 04bca5e (Update)
