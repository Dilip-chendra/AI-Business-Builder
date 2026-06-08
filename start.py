#!/usr/bin/env python3
"""
Autonomous Business Builder launcher.

One command for setup + start:
    python start.py

Useful extras:
    python start.py --skip-install
    python start.py --dev
    python start.py --status
    python start.py --stop
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
RUNTIME_DIR = ROOT / ".runtime"
LOG_DIR = RUNTIME_DIR / "logs"
PID_FILE = RUNTIME_DIR / "services.json"
STATE_FILE = RUNTIME_DIR / "state.json"

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    VENV_PIP = BACKEND_DIR / ".venv" / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
    VENV_PIP = BACKEND_DIR / ".venv" / "bin" / "pip"

BACKEND_URL = "http://127.0.0.1:8000/health"
FRONTEND_URL = "http://127.0.0.1:3000/login"


def _c(text: str, code: str) -> str:
    if IS_WINDOWS and not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"


def cyan(text: str) -> str:
    return _c(text, "96")


def green(text: str) -> str:
    return _c(text, "92")


def yellow(text: str) -> str:
    return _c(text, "93")


def red(text: str) -> str:
    return _c(text, "91")


def gray(text: str) -> str:
    return _c(text, "90")


def bold(text: str) -> str:
    return _c(text, "1")


def header(text: str) -> None:
    line = "=" * 66
    print(f"\n  {cyan(line)}")
    print(f"   {bold(text)}")
    print(f"  {cyan(line)}\n")


def step(n: int, total: int, text: str) -> None:
    print(f"{yellow(f'[{n}/{total}]')} {text}")


def ok(text: str) -> None:
    print(f"  {green('OK:')} {text}")


def warn(text: str) -> None:
    print(f"  {yellow('WARN:')} {text}")


def fail(text: str) -> None:
    print(f"  {red('ERROR:')} {text}")


def ensure_runtime_dirs() -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        check=check,
        env=env,
    )


def python_cmd() -> str:
    return shutil.which("python") or sys.executable


def npm_cmd() -> str:
    if IS_WINDOWS:
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def ensure_line(path: Path, key: str, value: str) -> None:
    lines = read_file(path).splitlines()
    updated = False
    changed = False
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}="):
            new_line = f"{key}={value}"
            if lines[idx] != new_line:
                lines[idx] = new_line
                changed = True
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
        changed = True
    if changed:
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def ensure_backend_env() -> None:
    env_path = BACKEND_DIR / ".env"
    example = BACKEND_DIR / ".env.example"
    if not env_path.exists() and example.exists():
        shutil.copy(example, env_path)
        ok("Created backend/.env from .env.example")
    elif env_path.exists():
        ok("backend/.env found")
    else:
        warn("backend/.env.example not found; creating minimal backend/.env")
        env_path.write_text("", encoding="utf-8")

    ensure_line(env_path, "FRONTEND_URL", "http://localhost:3000")
    ensure_line(env_path, "BACKEND_URL", "http://localhost:8000")
    ensure_line(env_path, "APP_BASE_URL", "http://localhost:3000")
    ensure_line(env_path, "API_BASE_URL", "http://localhost:8000")
    ensure_line(env_path, "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")


def ensure_frontend_env() -> None:
    env_path = FRONTEND_DIR / ".env.local"
    example = FRONTEND_DIR / ".env.example"
    if not env_path.exists() and example.exists():
        shutil.copy(example, env_path)
        ok("Created frontend/.env.local from .env.example")
    elif env_path.exists():
        ok("frontend/.env.local found")
    else:
        warn("frontend/.env.example not found; creating minimal frontend/.env.local")
        env_path.write_text("", encoding="utf-8")

    ensure_line(env_path, "NEXT_PUBLIC_API_URL", "http://localhost:8000/api/v1")


def check_python() -> None:
    ver = sys.version_info
    if ver < (3, 11):
        fail(f"Python 3.11+ required, found {ver.major}.{ver.minor}.{ver.micro}")
        raise SystemExit(1)
    ok(f"Python {ver.major}.{ver.minor}.{ver.micro}")


def check_node() -> None:
    if not command_exists("node"):
        fail("Node.js 18+ is required. Install it from https://nodejs.org")
        raise SystemExit(1)
    result = run(["node", "--version"], capture=True)
    ok(f"Node.js {result.stdout.strip()}")


def setup_venv(skip_install: bool) -> None:
    state = load_state()
    requirements_path = BACKEND_DIR / "requirements.txt"
    requirements_hash = file_hash(requirements_path)
    if not VENV_PYTHON.exists():
        print(f"  {gray('Creating backend virtual environment...')}")
        run([python_cmd(), "-m", "venv", str(BACKEND_DIR / ".venv")], check=True)
        ok("Virtual environment created")

    if skip_install:
        ok("Skipping backend dependency install")
        return

    if state.get("backend_requirements_hash") == requirements_hash:
        ok("Backend dependencies already up to date")
        return

    print(f"  {gray('Installing backend dependencies...')}")
    run(
        [str(VENV_PIP), "install", "--disable-pip-version-check", "--quiet", "-r", str(requirements_path)],
        check=True,
        capture=False,
    )
    state["backend_requirements_hash"] = requirements_hash
    save_state(state)
    ok("Backend dependencies ready")


def setup_frontend(skip_install: bool) -> None:
    state = load_state()
    node_modules = FRONTEND_DIR / "node_modules"
    package_lock = FRONTEND_DIR / "package-lock.json"
    package_json = FRONTEND_DIR / "package.json"
    frontend_deps_hash = hashlib.sha256((file_hash(package_json) + file_hash(package_lock)).encode("utf-8")).hexdigest()
    if skip_install and node_modules.exists():
        ok("Skipping frontend dependency install")
        return

    if node_modules.exists() and state.get("frontend_deps_hash") == frontend_deps_hash:
        ok("Frontend dependencies already up to date")
        return

    print(f"  {gray('Installing frontend dependencies...')}")
    run([npm_cmd(), "install", "--silent", "--no-fund", "--no-audit"], cwd=FRONTEND_DIR, check=True, capture=False)
    state["frontend_deps_hash"] = frontend_deps_hash
    save_state(state)
    ok("Frontend dependencies ready")


def ensure_playwright(skip_install: bool) -> None:
    state = load_state()
    requirements_hash = file_hash(BACKEND_DIR / "requirements.txt")
    if skip_install:
        ok("Skipping Playwright browser install")
        return
    if state.get("playwright_requirements_hash") == requirements_hash:
        ok("Chromium already installed for Playwright")
        return
    print(f"  {gray('Ensuring Chromium is installed for the browser agent...')}")
    run([str(VENV_PYTHON), "-m", "playwright", "install", "chromium"], cwd=BACKEND_DIR, check=True, capture=False)
    state["playwright_requirements_hash"] = requirements_hash
    save_state(state)
    ok("Chromium ready for Playwright")


def run_migrations() -> None:
    print(f"  {gray('Applying database migrations...')}")
    run([str(VENV_PYTHON), "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True, capture=False)
    ok("Database migrations applied")


def ensure_frontend_build(skip_install: bool, dev_mode: bool) -> None:
    if dev_mode:
        ok("Skipping production build in dev mode")
        return

    build_id = FRONTEND_DIR / ".next" / "BUILD_ID"
    source_mtime = latest_mtime(
        [
            FRONTEND_DIR / "app",
            FRONTEND_DIR / "components",
            FRONTEND_DIR / "hooks",
            FRONTEND_DIR / "lib",
            FRONTEND_DIR / "public",
            FRONTEND_DIR / "package.json",
            FRONTEND_DIR / "package-lock.json",
            FRONTEND_DIR / "next.config.mjs",
            FRONTEND_DIR / ".env.local",
        ]
    )
    if build_id.exists() and file_mtime(build_id) >= source_mtime:
        ok("Using existing frontend production build")
        ensure_standalone_assets()
        return

    print(f"  {gray('Building frontend production bundle...')}")
    run([npm_cmd(), "run", "build"], cwd=FRONTEND_DIR, check=True, capture=False)
    ok("Frontend build complete")
    ensure_standalone_assets()


def sync_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def ensure_standalone_assets() -> None:
    standalone_dir = FRONTEND_DIR / ".next" / "standalone"
    if not standalone_dir.exists():
        return

    static_src = FRONTEND_DIR / ".next" / "static"
    static_dst = standalone_dir / ".next" / "static"
    public_src = FRONTEND_DIR / "public"
    public_dst = standalone_dir / "public"

    sync_tree(static_src, static_dst)
    sync_tree(public_src, public_dst)

    if static_dst.exists() and public_dst.exists():
        ok("Standalone frontend static assets synced")
    elif not static_dst.exists():
        warn("Standalone frontend static assets are missing")


def is_url_ready(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ABB Launcher"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read(1024).decode("utf-8", errors="ignore")
        bad_markers = [
            "missing required error components",
            "Cannot GET /",
        ]
        return not any(marker in body for marker in bad_markers)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def wait_for_url(url: str, label: str, timeout: int) -> bool:
    print(f"  Waiting for {label}", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_url_ready(url):
            print(f" {green('Ready!')}")
            return True
        print(".", end="", flush=True)
        time.sleep(2)
    print(f" {red('Timed out')}")
    return False


def frontend_assets_ready() -> bool:
    try:
        req = urllib.request.Request(FRONTEND_URL, headers={"User-Agent": "ABB Launcher"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read(200_000).decode("utf-8", errors="ignore")

        assets = re.findall(r'/_next/static/[^"\'\\\s<>]+', html)
        if not assets:
            return False

        for asset in assets[:5]:
            asset_url = f"http://127.0.0.1:3000{asset}"
            req = urllib.request.Request(asset_url, headers={"User-Agent": "ABB Launcher"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status >= 400:
                    return False
        return True
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def save_runtime(data: dict[str, object]) -> None:
    ensure_runtime_dirs()
    PID_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_runtime() -> dict[str, object]:
    if not PID_FILE.exists():
        return {}
    try:
        return json.loads(PID_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_state() -> dict[str, object]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(data: dict[str, object]) -> None:
    ensure_runtime_dirs()
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_runtime() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def file_mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def latest_mtime(paths: list[Path]) -> float:
    latest = 0.0
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            latest = max(latest, file_mtime(path))
            continue
        for child in path.rglob("*"):
            if child.is_file():
                latest = max(latest, file_mtime(child))
    return latest


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if IS_WINDOWS:
            result = run(["tasklist", "/FI", f"PID eq {pid}"], capture=True)
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def kill_pid(pid: int | None) -> None:
    if not pid:
        return
    try:
        if IS_WINDOWS:
            run(["taskkill", "/F", "/PID", str(pid)], capture=True)
        else:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass


def kill_matching_processes() -> None:
    backend_patterns = [
        str(BACKEND_DIR).replace("\\", "\\\\"),
        str(VENV_PYTHON).replace("\\", "\\\\"),
        "app.main:app",
        "uvicorn",
    ]
    frontend_patterns = [
        str(FRONTEND_DIR).replace("\\", "\\\\"),
        "next start",
        "next dev",
        "npm run start",
        "npm run dev",
        ".next\\standalone\\server.js",
    ]
    if IS_WINDOWS:
        ps_script = f"""
$backendPatterns = @({", ".join(f"'{pattern}'" for pattern in backend_patterns)})
$frontendPatterns = @({", ".join(f"'{pattern}'" for pattern in frontend_patterns)})
Get-CimInstance Win32_Process | ForEach-Object {{
  $cmd = $_.CommandLine
  if (-not $cmd) {{ return }}
  $shouldStop = $false
  foreach ($pattern in $backendPatterns + $frontendPatterns) {{
    if ($cmd -like "*$pattern*") {{
      $shouldStop = $true
      break
    }}
  }}
  if ($shouldStop) {{
    try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{ }}
  }}
}}
"""
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    else:
        for pattern in (str(BACKEND_DIR), "uvicorn app.main:app", str(FRONTEND_DIR), "next start", "next dev"):
            subprocess.run(["pkill", "-f", pattern], capture_output=True)


def kill_port(port: int) -> None:
    for pid in port_owners(port):
        kill_pid(pid)
    if not IS_WINDOWS:
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=10)
        except Exception:
            pass


def port_owner(port: int) -> int | None:
    owners = port_owners(port)
    return owners[0] if owners else None


def port_owners(port: int) -> list[int]:
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            owners: set[int] = set()
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) < 5 or not parts[0].upper().startswith("TCP"):
                    continue
                local_address = parts[1]
                state = parts[3].upper()
                pid = parts[4]
                if not local_address.endswith(f":{port}"):
                    continue
                if state not in {"LISTENING", "ESTABLISHED"}:
                    continue
                if pid.isdigit():
                    owners.add(int(pid))
            return sorted(owners)
        result = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True, timeout=10)
        owners = []
        for line in result.stdout.splitlines():
            if line.strip().isdigit():
                owners.append(int(line.strip()))
        return owners
    except Exception:
        return []


def kill_port_family(port: int) -> None:
    owner = port_owner(port)
    if owner is None:
        return
    if IS_WINDOWS:
        ps_script = f"""
$owner = {owner}
Get-CimInstance Win32_Process | Where-Object {{
  $_.ProcessId -eq $owner -or $_.ParentProcessId -eq $owner
}} | ForEach-Object {{
  try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{ }}
}}
"""
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        except Exception:
            kill_pid(owner)
    else:
        try:
            os.kill(owner, signal.SIGTERM)
        except Exception:
            pass


def tail_log(path: Path, max_lines: int = 20) -> str:
    if not path.exists():
        return "(log file missing)"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-max_lines:]).strip() or "(no log output yet)"


def start_process(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    ensure_runtime_dirs()
    log_handle = log_path.open("wb")
    if IS_WINDOWS:
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        return subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            env=env,
        )
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )


def backend_command(dev_mode: bool) -> list[str]:
    cmd = [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio"]
    if dev_mode:
        cmd.append("--reload")
    return cmd


def frontend_command(dev_mode: bool) -> list[str]:
    if dev_mode:
        return [npm_cmd(), "run", "dev"]
    standalone_server = FRONTEND_DIR / ".next" / "standalone" / "server.js"
    if standalone_server.exists():
        return ["node", str(standalone_server)]
    return [npm_cmd(), "run", "start"]


def start_backend(dev_mode: bool) -> tuple[int, Path]:
    log_path = LOG_DIR / "backend.log"
    proc = start_process(backend_command(dev_mode), cwd=BACKEND_DIR, log_path=log_path, env=os.environ.copy())
    ok(f"Backend process started (PID {proc.pid})")
    return proc.pid, log_path


def start_frontend(dev_mode: bool) -> tuple[int, Path]:
    log_path = LOG_DIR / "frontend.log"
    env = os.environ.copy()
    env.setdefault("NODE_ENV", "development" if dev_mode else "production")
    proc = start_process(frontend_command(dev_mode), cwd=FRONTEND_DIR, log_path=log_path, env=env)
    ok(f"Frontend process started (PID {proc.pid})")
    return proc.pid, log_path


def check_and_start_ollama() -> tuple[int | None, Path | None]:
    if not command_exists("ollama"):
        warn("Ollama not found. The app can still use Groq or Hugging Face.")
        return None, None

    if is_url_ready("http://127.0.0.1:11434/api/tags"):
        ok("Ollama already running")
        return None, None

    log_path = LOG_DIR / "ollama.log"
    if IS_WINDOWS:
        proc = start_process(["ollama", "serve"], cwd=ROOT, log_path=log_path)
    else:
        proc = start_process(["ollama", "serve"], cwd=ROOT, log_path=log_path)
    ok(f"Ollama process started (PID {proc.pid})")
    wait_for_url("http://127.0.0.1:11434/api/tags", "Ollama", timeout=20)
    return proc.pid, log_path


def open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        warn(f"Could not open browser automatically. Open {url} manually.")


def status() -> int:
    runtime = load_runtime()
    header("AUTONOMOUS BUSINESS BUILDER STATUS")
    backend_pid = runtime.get("backend_pid")
    frontend_pid = runtime.get("frontend_pid")
    ollama_pid = runtime.get("ollama_pid")
    backend_owner = port_owner(8000)
    frontend_owner = port_owner(3000)
    backend_alive = backend_owner is not None or (pid_alive(int(backend_pid)) if isinstance(backend_pid, int) else False)
    frontend_alive = frontend_owner is not None or (pid_alive(int(frontend_pid)) if isinstance(frontend_pid, int) else False)

    print(f"  Backend PID:   {backend_pid or '-'}")
    print(f"  Frontend PID:  {frontend_pid or '-'}")
    print(f"  Ollama PID:    {ollama_pid or '-'}")
    print(f"  Backend port owner:   {backend_owner or '-'}")
    print(f"  Frontend port owner:  {frontend_owner or '-'}")
    print()
    print(f"  Backend health:   {green('up') if is_url_ready(BACKEND_URL) else red('down')}")
    print(f"  Frontend health:  {green('up') if is_url_ready(FRONTEND_URL) else red('down')}")
    print(f"  Backend process:  {green('alive') if backend_alive else red('dead')}")
    print(f"  Frontend process: {green('alive') if frontend_alive else red('dead')}")
    return 0


def stop_services() -> int:
    header("STOPPING AUTONOMOUS BUSINESS BUILDER")
    runtime = load_runtime()
    for key in ("frontend_pid", "backend_pid", "ollama_pid"):
        pid = runtime.get(key)
        if isinstance(pid, int) and pid_alive(pid):
            kill_pid(pid)
            ok(f"Stopped {key.replace('_pid', '')} (PID {pid})")
    for port in (3000, 8000):
        try:
            kill_port_family(port)
        except Exception:
            warn(f"Could not inspect port {port}; continuing shutdown.")
    try:
        kill_matching_processes()
    except Exception:
        warn("Could not scan matching processes; continuing shutdown.")
    time.sleep(1)
    for port in (3000, 8000):
        try:
            kill_port(port)
        except Exception:
            warn(f"Could not force-clear port {port}; it may already be free.")
    remove_runtime()
    ok("Ports 3000 and 8000 cleared")
    return 0


def launch(skip_install: bool, no_browser: bool, backend_only: bool, frontend_only: bool, no_ollama: bool, dev_mode: bool) -> int:
    total = 10
    current = 1

    header("AUTONOMOUS BUSINESS BUILDER - FULL STACK LAUNCHER")

    step(current, total, "Checking Python..."); current += 1
    check_python()

    step(current, total, "Checking Node.js..."); current += 1
    check_node()

    step(current, total, "Preparing environment files..."); current += 1
    ensure_backend_env()
    ensure_frontend_env()

    step(current, total, "Setting up backend virtual environment..."); current += 1
    setup_venv(skip_install)

    step(current, total, "Setting up frontend dependencies..."); current += 1
    setup_frontend(skip_install)

    step(current, total, "Installing browser agent prerequisites..."); current += 1
    ensure_playwright(skip_install)

    step(current, total, "Running database migrations..."); current += 1
    run_migrations()

    ollama_pid: int | None = None
    if not no_ollama:
        step(current, total, "Checking Ollama..."); current += 1
        ollama_pid, _ = check_and_start_ollama()
    else:
        step(current, total, "Checking Ollama..."); current += 1
        warn("Skipping Ollama by request")

    backend_pid: int | None = None
    frontend_pid: int | None = None
    backend_log = LOG_DIR / "backend.log"
    frontend_log = LOG_DIR / "frontend.log"

    step(current, total, "Starting backend server..."); current += 1
    if not frontend_only:
        kill_port(8000)
        time.sleep(1)
        backend_pid, _ = start_backend(dev_mode)
        if not wait_for_url(BACKEND_URL, "backend API", timeout=90):
            fail("Backend did not become healthy. Last backend log lines:")
            print(tail_log(backend_log))
            return 1
    else:
        warn("Skipping backend")

    step(current, total, "Starting frontend server..."); current += 1
    if not backend_only:
        kill_port(3000)
        time.sleep(1)
        ensure_frontend_build(skip_install, dev_mode)
        frontend_pid, _ = start_frontend(dev_mode)
        if not wait_for_url(FRONTEND_URL, "frontend app", timeout=180 if dev_mode else 60):
            fail("Frontend did not become healthy. Last frontend log lines:")
            print(tail_log(frontend_log))
            return 1
        if not dev_mode and not frontend_assets_ready():
            fail("Frontend HTML loaded, but Next.js static assets are unavailable.")
            fail("The app would render as raw HTML. Last frontend log lines:")
            print(tail_log(frontend_log))
            return 1
        if not dev_mode:
            ok("Frontend static assets verified")
    else:
        warn("Skipping frontend")

    existing_runtime = load_runtime()
    save_runtime(
        {
            "backend_pid": backend_pid if backend_pid is not None else existing_runtime.get("backend_pid"),
            "frontend_pid": frontend_pid if frontend_pid is not None else existing_runtime.get("frontend_pid"),
            "ollama_pid": ollama_pid if ollama_pid is not None else existing_runtime.get("ollama_pid"),
            "backend_log": str(backend_log if backend_pid is not None else existing_runtime.get("backend_log", backend_log)),
            "frontend_log": str(frontend_log if frontend_pid is not None else existing_runtime.get("frontend_log", frontend_log)),
            "started_at": int(time.time()),
            "dev_mode": dev_mode,
        }
    )

    header("ALL SERVICES RUNNING")
    if not backend_only:
        print(f"  Frontend:  {cyan('http://localhost:3000')}")
    if not frontend_only:
        print(f"  Backend:   {cyan('http://localhost:8000')}")
        print(f"  API Docs:  {cyan('http://localhost:8000/api/docs')}")
    print(f"  Logs:      {cyan(str(LOG_DIR))}")
    print()
    print(f"  {gray('Use `python start.py --status` to inspect services')}")
    print(f"  {gray('Use `python start.py --stop` to stop them')}")
    print()

    if not no_browser and not backend_only:
        print(f"  {gray('Opening app in browser...')}")
        open_browser("http://localhost:3000/login")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Business Builder launcher")
    parser.add_argument("--skip-install", action="store_true", help="Skip npm/pip install steps")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--backend-only", action="store_true", help="Start only the backend API")
    parser.add_argument("--frontend-only", action="store_true", help="Start only the frontend app")
    parser.add_argument("--no-ollama", action="store_true", help="Do not start Ollama")
    parser.add_argument("--dev", action="store_true", help="Run frontend and backend in dev mode")
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--stop", action="store_true", help="Stop started services")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_runtime_dirs()

    if args.status:
        return status()
    if args.stop:
        return stop_services()
    if args.backend_only and args.frontend_only:
        fail("Choose either --backend-only or --frontend-only, not both.")
        return 1

    return launch(
        skip_install=args.skip_install,
        no_browser=args.no_browser,
        backend_only=args.backend_only,
        frontend_only=args.frontend_only,
        no_ollama=args.no_ollama,
        dev_mode=args.dev,
    )


if __name__ == "__main__":
    raise SystemExit(main())
