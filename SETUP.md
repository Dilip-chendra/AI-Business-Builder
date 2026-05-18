# AI Autonomous Business Builder — Full Setup Guide

Run these commands in order to get the app fully working from scratch.

---

## Prerequisites

- Python 3.14+ installed
- Node.js 18+ installed
- Git (optional)

---

## Step 1 — Install Ollama (Local AI — Free, No API Key)

```powershell
# Download and install from https://ollama.com
# Then pull the model:
ollama pull llama3
# Verify it's running:
ollama list
```

---

## Step 2 — Backend Setup

```powershell
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install all dependencies
pip install fastapi>=0.115.0 uvicorn[standard]>=0.30.0 starlette>=0.40.0
pip install sqlalchemy[asyncio]>=2.0.30 aiosqlite>=0.20.0
pip install pydantic>=2.11.0 pydantic-settings>=2.5.0
pip install openai>=1.35.0 httpx>=0.27.0
pip install stripe>=9.12.0 alembic>=1.13.0
pip install bcrypt>=4.1.3 "python-jose[cryptography]>=3.3.0" python-multipart>=0.0.9
pip install redis>=5.0.0 aiosmtplib>=3.0.0 celery>=5.4.0
pip install playwright>=1.44.0
pip install pytest>=8.2.0 pytest-asyncio>=0.23.0

# Install Playwright browser
.venv\Scripts\playwright install chromium

# Copy environment file
copy .env.example .env
```

---

## Step 3 — Configure Environment (backend/.env)

Open `backend/.env` and set these values:

```env
# Database (SQLite works out of the box)
DATABASE_URL=sqlite+aiosqlite:///./autonomous_builder.db

# AI Providers — set at least ONE:
# Option A: Groq (free, fastest) — get key at https://console.groq.com
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Option B: HuggingFace (free) — get token at https://huggingface.co/settings/tokens
HF_API_KEY=your_hf_key_here
HF_MODEL=mistralai/Mistral-7B-Instruct-v0.3

# Option C: Ollama (local, no key needed — just run ollama pull llama3)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Rate limiting (increase for development)
RATE_LIMIT_REQUESTS=500
RATE_LIMIT_WINDOW_SECONDS=3600

# JWT (change in production)
JWT_SECRET_KEY=change-me-in-production-use-a-long-random-string
```

---

## Step 4 — Initialize Database

```powershell
# Still in backend/ directory with .venv activated
.venv\Scripts\alembic upgrade head
```

If you get "table already exists" errors:
```powershell
.venv\Scripts\alembic stamp head
```

---

## Step 5 — Start Backend

```powershell
# In backend/ directory
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

Verify it's running:
- Health: http://localhost:8000/health
- AI Status: http://localhost:8000/api/v1/ai/health
- Swagger docs: http://localhost:8000/api/docs

---

## Step 6 — Frontend Setup

```powershell
# Open a NEW terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Copy environment file
copy .env.example .env.local
```

The `.env.local` should contain:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Step 7 — Start Frontend

```powershell
# In frontend/ directory
npm run dev
```

App is now running at: **http://localhost:3000**

---

## Step 8 — Create Your First Account

1. Go to http://localhost:3000
2. Click **Get Started Free**
3. Sign up with any email/password
4. You're in!

---

## Step 9 — Generate Your First Business

1. Go to **Generator** in the sidebar
2. Fill in your interests (e.g. "fitness coaching")
3. Click **Generate My Business**
4. Wait ~2 seconds for Groq to generate
5. You'll be redirected to your live landing page

---

## Step 10 — Test All Features

| Feature | URL | What to do |
|---------|-----|------------|
| Dashboard | /dashboard | See your businesses |
| Generator | /generator | Create a new business |
| Agent Live | /agent-live | Run AI agent with live visualization |
| AI Playground | /ai-playground | Chat with AI to modify your landing page |
| Products | /products | Add products to your business |
| Marketing | /marketing | Generate campaigns, SEO content, ads |
| Support | /support | Test AI customer support chatbot |
| Analytics | /analytics | View traffic and conversion data |
| AI Status | /ai-status | Check which AI providers are active |

---

## Troubleshooting

### "No AI provider available" (503 error)
- Make sure Ollama is running: `ollama serve`
- Or set `GROQ_API_KEY` in `backend/.env`
- Check: http://localhost:8000/api/v1/ai/health

### "Rate limit exceeded" (429 error)
- Set `RATE_LIMIT_REQUESTS=500` in `backend/.env`
- Restart the backend

### "Table already exists" (Alembic error)
```powershell
.venv\Scripts\alembic stamp head
```

### Frontend can't connect to backend
- Make sure backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `frontend/.env.local`

### Playwright/Browser agent not working
```powershell
.venv\Scripts\playwright install chromium
```

### PowerShell execution policy error
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Quick Restart (after initial setup)

**Terminal 1 — Backend:**
```powershell
cd backend
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```

**Terminal 3 — Ollama (if using local AI):**
```powershell
ollama serve
```

---

## Production Deployment

For production, additionally set:
```env
APP_ENV=production
JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(64))">
DATABASE_URL=postgresql://user:pass@host/db
STRIPE_SECRET_KEY=sk_live_...
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_smtp_password
```
