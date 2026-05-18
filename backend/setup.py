"""
Autonomous Business Builder — automated backend setup script.

Run from the backend/ directory:
    python setup.py

What it does:
  1. Creates a virtual environment (.venv) if one doesn't exist
  2. Installs all Python dependencies
  3. Copies .env.example → .env if .env doesn't exist
  4. Initialises the SQLite database (runs Alembic migrations)
  5. Checks AI provider availability and prints a summary
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VENV = HERE / ".venv"
PYTHON = VENV / ("Scripts" if sys.platform == "win32" else "bin") / "python"
PIP = VENV / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
ALEMBIC = VENV / ("Scripts" if sys.platform == "win32" else "bin") / "alembic"


def run(cmd: list[str], **kwargs) -> int:
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    return result.returncode


def step(msg: str) -> None:
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def main() -> None:
    # ── 1. Virtual environment ────────────────────────────────────────────────
    step("1/5  Setting up virtual environment")
    if not VENV.exists():
        rc = run([sys.executable, "-m", "venv", str(VENV)])
        if rc != 0:
            print("ERROR: Failed to create virtual environment.")
            sys.exit(1)
        print("Virtual environment created.")
    else:
        print("Virtual environment already exists — skipping.")

    # ── 2. Install dependencies ───────────────────────────────────────────────
    step("2/5  Installing Python dependencies")
    rc = run([str(PIP), "install", "--quiet", "-r", "requirements.txt"])
    if rc != 0:
        print("ERROR: pip install failed. Check requirements.txt and your internet connection.")
        sys.exit(1)
    print("Dependencies installed.")

    # ── 3. Environment file ───────────────────────────────────────────────────
    step("3/5  Configuring environment")
    env_file = HERE / ".env"
    env_example = HERE / ".env.example"
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print(f"Created .env from .env.example")
            print("IMPORTANT: Open backend/.env and set at least one AI provider key:")
            print("  GROQ_API_KEY=  (free at console.groq.com)")
            print("  HF_API_KEY=    (free at huggingface.co/settings/tokens)")
        else:
            print("WARNING: .env.example not found. Create backend/.env manually.")
    else:
        print(".env already exists — skipping.")

    # ── 4. Database initialisation ────────────────────────────────────────────
    step("4/5  Initialising database")
    if ALEMBIC.exists():
        rc = run([str(ALEMBIC), "upgrade", "head"], cwd=str(HERE))
        if rc != 0:
            print("WARNING: Alembic migration failed. The app will still start with SQLite auto-create.")
        else:
            print("Database schema is up to date.")
    else:
        print("WARNING: alembic not found in venv. Run pip install -r requirements.txt first.")

    # ── 5. AI provider check ──────────────────────────────────────────────────
    step("5/5  Checking AI provider configuration")
    _check_ai_providers(env_file)

    # ── Done ──────────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  Setup complete!")
    print("="*60)
    print("\nTo start the backend server:")
    if sys.platform == "win32":
        print(f"  cd backend")
        print(f"  .venv\\Scripts\\activate.bat")
        print(f"  uvicorn app.main:app --reload")
    else:
        print(f"  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload")
    print("\nAPI docs: http://localhost:8000/api/docs")
    print("AI status: http://localhost:3000/ai-status  (after starting frontend)")


def _check_ai_providers(env_file: Path) -> None:
    """Read .env and report which AI providers are configured."""
    env_vars: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()

    groq = bool(env_vars.get("GROQ_API_KEY", "").strip())
    hf = bool(env_vars.get("HF_API_KEY", "").strip())
    ollama_url = env_vars.get("OLLAMA_BASE_URL", "http://localhost:11434")

    # Quick Ollama check
    ollama = False
    try:
        import urllib.request
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=2)
        ollama = True
    except Exception:
        pass

    print(f"  Groq API key:      {'✓ configured' if groq else '✗ not set  (set GROQ_API_KEY)'}")
    print(f"  HuggingFace key:   {'✓ configured' if hf else '✗ not set  (set HF_API_KEY)'}")
    print(f"  Ollama (local):    {'✓ running' if ollama else '✗ not running  (optional)'}")

    if not groq and not hf and not ollama:
        print("\n  ⚠  WARNING: No AI provider is available.")
        print("     Business generation will return 503 until you configure one.")
        print("     Quickest option: get a free Groq key at https://console.groq.com")
    else:
        active = [n for n, ok in [("Groq", groq), ("HuggingFace", hf), ("Ollama", ollama)] if ok]
        print(f"\n  ✓ AI is ready. Active providers: {', '.join(active)}")


if __name__ == "__main__":
    main()
