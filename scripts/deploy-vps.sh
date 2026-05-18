#!/usr/bin/env bash
set -euo pipefail

echo "Building production images..."
docker compose build backend worker browser-agent frontend

echo "Starting core infrastructure..."
docker compose up -d postgres redis ollama

echo "Warming Ollama models..."
docker compose up -d ollama-init

echo "Running migrations..."
docker compose run --rm backend alembic upgrade head

echo "Starting application services..."
docker compose up -d backend worker browser-agent beat frontend nginx

echo "Deployment complete."
echo "Health: $(curl -fsS http://localhost/health || true)"
