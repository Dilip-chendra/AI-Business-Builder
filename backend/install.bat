@echo off
echo ============================================================
echo  Autonomous Business Builder - Backend Setup
echo ============================================================
echo.

REM Show Python version
python --version

REM Create venv if missing
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created.
)

REM Upgrade pip
echo Upgrading pip...
.venv\Scripts\python -m pip install --upgrade pip --quiet

REM Install core packages (all have Python 3.14 wheels)
echo Installing core packages...
.venv\Scripts\pip install ^
    "fastapi>=0.115.0" ^
    "uvicorn[standard]>=0.30.0" ^
    "sqlalchemy[asyncio]>=2.0.30" ^
    "aiosqlite>=0.20.0" ^
    "pydantic>=2.11.0" ^
    "pydantic-settings>=2.5.0" ^
    "openai>=1.35.0" ^
    "httpx>=0.27.0" ^
    "stripe>=9.12.0" ^
    "alembic>=1.13.0" ^
    "bcrypt>=4.1.3" ^
    "python-jose[cryptography]>=3.3.0" ^
    "python-multipart>=0.0.9" ^
    "redis>=5.0.0" ^
    "aiosmtplib>=3.0.0" ^
    "celery>=5.4.0" ^
    "pytest>=8.2.0" ^
    "pytest-asyncio>=0.23.0"

if errorlevel 1 (
    echo ERROR: Core package installation failed.
    pause
    exit /b 1
)
echo Core packages installed successfully.

REM Install playwright separately (large download)
echo.
echo Installing Playwright (browser automation)...
.venv\Scripts\pip install "playwright>=1.44.0"
if errorlevel 1 (
    echo WARNING: Playwright install failed - Browser Agent will not work.
) else (
    echo Installing Chromium browser...
    .venv\Scripts\playwright install chromium
    if errorlevel 1 (
        echo WARNING: Chromium install failed. Run manually: .venv\Scripts\playwright install chromium
    ) else (
        echo Chromium installed successfully.
    )
)

REM Copy .env if missing
if not exist ".env" (
    echo.
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo *** Ollama is running with llama3 - AI works immediately! ***
    echo To add faster cloud AI: set GROQ_API_KEY in backend\.env
)

REM Run migrations
echo.
echo Initialising database...
.venv\Scripts\alembic upgrade head
if errorlevel 1 (
    echo WARNING: Alembic migration failed.
    echo SQLite tables will be created automatically on first request.
)

echo.
echo ============================================================
echo  Setup complete!
echo  Run: .\start_backend.bat
echo ============================================================
pause
