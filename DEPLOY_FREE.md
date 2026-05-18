# Closest Free Deployment Path

This is the closest fully cloud-hosted path that stays online after your laptop is off without paying for a VPS:

- **Platform:** Render
- **Services:** 2 free web services + 1 free Postgres + 1 free Key Value
- **Repo import:** uses the root [`render.yaml`](C:/Users/admin/Downloads/Autonomous%20Business%20Builder/render.yaml)

Important reality check:

- Render free services are good for demos and evaluation, **not** true production.
- Free web services can sleep and wake up slowly.
- Free Key Value does **not** persist data to disk.
- There is **no free Ollama hosting** in this path, so cloud AI relies on Featherless / Groq / HuggingFace.

Official references:

- [Render free instances](https://render.com/docs/free)
- [Render Blueprint spec](https://render.com/docs/blueprint-spec)
- [Deploy to Render](https://render.com/docs/deploy-to-render)

## What this blueprint deploys

The included [`render.yaml`](C:/Users/admin/Downloads/Autonomous%20Business%20Builder/render.yaml) creates:

1. `ai-business-builder-web`  
   Next.js frontend on a free Render web service
2. `ai-business-builder-api`  
   FastAPI backend on a free Render web service
3. `ai-business-builder-db`  
   free Render Postgres
4. `ai-business-builder-cache`  
   free Render Key Value

The frontend proxies `/api/*` and `/uploads/*` to the backend over Render’s internal network, so users only need the frontend public URL.

## One-click import

Open this on any device while logged into your Render account:

[Deploy the repo on Render](https://render.com/deploy?repo=https://github.com/Dilip-chendra/Autonomous-Business-Builder.git)

## Values you will be prompted for

During the first Blueprint import, Render will ask for secret values because the blueprint uses `sync: false`.

You should prepare:

- `FEATHERLESS_API_KEY`
- `ENCRYPTION_KEY`
- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `PAYPAL_WEBHOOK_ID` if you want live PayPal webhooks
- `LINKEDIN_CLIENT_ID`
- `LINKEDIN_CLIENT_SECRET`
- `NEXT_PUBLIC_PAYPAL_CLIENT_ID`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`

Generate `ENCRYPTION_KEY` locally with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## After the first deploy finishes

Render will give you two public URLs, one for:

- `ai-business-builder-web`
- `ai-business-builder-api`

Open the **backend service** environment variables and set:

```env
FRONTEND_URL=https://YOUR-FRONTEND.onrender.com
BACKEND_URL=https://YOUR-BACKEND.onrender.com
APP_BASE_URL=https://YOUR-FRONTEND.onrender.com
API_BASE_URL=https://YOUR-BACKEND.onrender.com/api
CORS_ORIGINS=https://YOUR-FRONTEND.onrender.com
TRUSTED_HOSTS=YOUR-FRONTEND.onrender.com,YOUR-BACKEND.onrender.com,localhost,127.0.0.1
LINKEDIN_REDIRECT_URI=https://YOUR-BACKEND.onrender.com/api/v1/integrations/linkedin/callback
```

Then manually redeploy the backend service once.

## Final smoke test

After both services are healthy:

1. Open the frontend public URL
2. Sign up / log in
3. Generate a business
4. Open Marketing
5. Open Agent Live
6. Open Billing
7. Open Integrations

## What works well on this free path

- frontend
- backend API
- PostgreSQL persistence
- Redis-compatible cache / queues
- Featherless / Groq / HuggingFace cloud AI
- most business generation and marketing generation flows
- browser research flows that run inside request limits

## What is limited on this free path

- cold starts
- long-running browser automation
- reliable queue persistence
- local Ollama models
- true production traffic

## If you want the better next step

When you outgrow the free path, move the same repo to:

- 1 Ubuntu VPS with Docker Compose
- or Render paid web + worker services

The repo already includes the stronger path in [DEPLOYMENT.md](C:/Users/admin/Downloads/Autonomous%20Business%20Builder/DEPLOYMENT.md).
