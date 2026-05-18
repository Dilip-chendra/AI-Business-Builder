FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY backend/gunicorn_conf.py ./gunicorn_conf.py

RUN mkdir -p uploads .runtime/browser-sessions workspace

CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info", "-Q", "browser", "--concurrency=1", "--prefetch-multiplier=1"]
