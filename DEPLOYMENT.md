# Production Deployment Guide

This stack is designed for an Ubuntu VPS using Docker Compose and an external domain.

## Architecture

- `frontend`: Next.js 14 standalone runtime
- `backend`: FastAPI served by Gunicorn + Uvicorn workers
- `worker`: Celery worker for AI, analytics, campaigns
- `browser-agent`: isolated Playwright worker for browser automation
- `beat`: Celery Beat scheduler
- `postgres`: primary relational database
- `redis`: cache and queue broker
- `ollama`: local model runtime
- `nginx`: reverse proxy for frontend, API, SSE, and uploads
- `prometheus` / `grafana`: optional observability profile

## 1. Ubuntu VPS Setup

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

## 2. Clone the Repo

```bash
git clone <your-repo-url> ai-business-builder
cd ai-business-builder
```

## 3. Create Runtime Environment Files

Create `backend/.env` from `backend/.env.example` and set production-safe values.

Required values:

```env
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://abb:<strong-password>@postgres:5432/ai_business_builder
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
JWT_SECRET_KEY=<long-random-secret>
ENCRYPTION_KEY=<fernet-key>
PAYPAL_CLIENT_ID=<paypal-client-id>
PAYPAL_CLIENT_SECRET=<paypal-secret>
LINKEDIN_CLIENT_ID=<linkedin-client-id>
LINKEDIN_CLIENT_SECRET=<linkedin-client-secret>
OLLAMA_BASE_URL=http://ollama:11434
TRUSTED_HOSTS=your-domain.com,www.your-domain.com,localhost,backend,nginx
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://your-domain.com
APP_BASE_URL=https://your-domain.com
API_BASE_URL=https://your-domain.com/api
```

Optional root shell env for Compose:

```bash
export POSTGRES_DB=ai_business_builder
export POSTGRES_USER=abb
export POSTGRES_PASSWORD='<strong-password>'
export NEXT_PUBLIC_API_URL='https://your-domain.com/api/v1'
export NEXT_PUBLIC_PAYPAL_CLIENT_ID='<paypal-client-id>'
```

## 4. Build and Start the Platform

```bash
docker compose build
docker compose up -d postgres redis ollama
docker compose up -d ollama-init
docker compose up -d backend worker browser-agent beat frontend nginx
```

## 5. Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

## 6. Validate Health

```bash
curl http://localhost/health
curl http://localhost/ready
docker compose ps
docker compose logs backend --tail=200
```

## 7. SSL Setup

This repo ships with HTTP nginx proxying by default so the stack starts cleanly everywhere.

For production HTTPS, put the app behind either:

1. Cloudflare / managed load balancer, or
2. host-level Certbot + nginx override, or
3. a separate reverse proxy like Traefik / Caddy.

Recommended fast path with Certbot on host:

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
```

Then extend the nginx config to mount:

- `/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- `/etc/letsencrypt/live/your-domain.com/privkey.pem`

and expose port `443:443`.

## 8. Observability

Start dashboards only when needed:

```bash
docker compose --profile observability up -d prometheus grafana
```

- Prometheus: `http://your-server:9090`
- Grafana: `http://your-server:3001`

## 9. Backups

Database backup:

```bash
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Database restore:

```bash
cat backup.sql | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

## 10. Zero-Downtime-ish Update Flow

```bash
git pull
docker compose build backend worker browser-agent frontend
docker compose exec backend alembic upgrade head
docker compose up -d backend worker browser-agent beat frontend nginx
```

## 11. Recommended Production Practices

- put nginx behind Cloudflare or a managed LB
- rotate secrets regularly
- mount persistent volumes for `postgres`, `redis`, `ollama`, uploads, browser sessions, and workspace
- keep `browser-agent` isolated from web-serving workers
- monitor `/ready`, queue depth, and browser-agent failure rate
- warm Ollama models during deploy using `ollama-init`
