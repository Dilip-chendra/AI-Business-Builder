@echo off
echo ============================================================
echo  Autonomous Business Builder Backend
echo ============================================================
echo  API docs:      http://localhost:8000/api/docs
echo  Health:        http://localhost:8000/health
echo  AI status:     http://localhost:8000/api/v1/ai/health
echo  Agent run:     POST http://localhost:8000/api/v1/agent/run
echo  Browser agent: POST http://localhost:8000/api/v1/agent/browser/run
echo ============================================================
echo.
REM Windows requires SelectorEventLoop for Playwright subprocess support
set PYTHONASYNCIODEBUG=0
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
