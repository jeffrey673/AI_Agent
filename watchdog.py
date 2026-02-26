"""
SKIN1004 AI — Service Watchdog
================================
Monitors FastAPI, Open WebUI, and Reverse Proxy every 60 seconds.
Automatically restarts failed services and checks model availability.

Usage:
    python watchdog.py
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

# ── Config ────────────────────────────────────────────────
CHECK_INTERVAL = 60        # seconds between checks
RESTART_WAIT = 30          # seconds to wait after restart before re-check
COOLDOWN = 300             # 5 min cooldown after 3 consecutive failures
MAX_CONSECUTIVE_FAILS = 3  # failures before cooldown

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("watchdog")

# ── Service definitions ───────────────────────────────────
SERVICES = {
    "fastapi": {
        "url": "http://localhost:8100/health",
        "port": 8100,
        "cmd": [
            "cmd", "/k",
            "cd /d C:\\Users\\DB_PC\\Desktop\\python_bcj\\AI_Agent && "
            "python -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload",
        ],
        "window_title": "FastAPI AI (8100)",
    },
    "openwebui": {
        "url": "http://localhost:8080",
        "port": 8080,
        "cmd": [
            "cmd", "/k",
            "cd /d C:\\Users\\DB_PC\\Desktop\\python_bcj\\AI_Agent && "
            "set DATA_DIR=C:\\Users\\DB_PC\\.open-webui\\data && "
            "set PYTHONUTF8=1 && "
            "set PYTHONIOENCODING=utf-8 && "
            "set ENABLE_VERSION_UPDATE_CHECK=false && "
            "set OPENAI_API_BASE_URLS=http://localhost:8100/v1 && "
            "set OPENAI_API_KEYS=sk-skin1004 && "
            "open-webui serve --port 8080",
        ],
        "window_title": "Open WebUI (8080)",
    },
    "proxy": {
        "url": "http://localhost:3000",
        "port": 3000,
        "cmd": [
            "cmd", "/k",
            "cd /d C:\\Users\\DB_PC\\Desktop\\python_bcj\\AI_Agent && "
            "python -X utf8 proxy.py",
        ],
        "window_title": "Proxy (3000)",
    },
}

# Failure tracking per service
_fail_counts: dict[str, int] = {k: 0 for k in SERVICES}
_cooldown_until: dict[str, float] = {k: 0.0 for k in SERVICES}


def _http_check(url: str, timeout: int = 5) -> bool:
    """Return True if URL responds with 2xx."""
    try:
        resp = urlopen(url, timeout=timeout)
        return 200 <= resp.status < 400
    except Exception:
        return False


def _check_models() -> bool:
    """Check if skin1004 models are available via proxy /api/models."""
    try:
        resp = urlopen("http://localhost:3000/api/models", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        # Open WebUI returns {"data": [...]} with model objects
        models = data.get("data", [])
        model_ids = [m.get("id", "") for m in models]
        has_skin1004 = any("skin1004" in mid.lower() for mid in model_ids)
        if not has_skin1004:
            log.warning("model_check_failed: skin1004 models not found in %s", model_ids)
        return has_skin1004
    except Exception as e:
        log.warning("model_check_error: %s", e)
        return False


def _kill_port(port: int) -> None:
    """Kill processes listening on a specific port."""
    try:
        result = subprocess.run(
            f'netstat -aon | findstr ":{port} " | findstr "LISTENING"',
            shell=True, capture_output=True, text=True,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                pid = parts[-1]
                subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                               capture_output=True)
                log.info("killed_pid=%s on port %d", pid, port)
    except Exception as e:
        log.warning("kill_port_error port=%d: %s", port, e)


def _restart_service(name: str) -> None:
    """Kill existing process on port, then start the service in a new window."""
    svc = SERVICES[name]
    log.info("restarting %s (port %d)...", name, svc["port"])

    # Kill existing process on port
    _kill_port(svc["port"])
    time.sleep(2)

    # Start new process
    subprocess.Popen(
        ["start", svc["window_title"]] + svc["cmd"],
        shell=True,
        cwd=str(BASE_DIR),
    )
    log.info("started %s", name)


def _handle_failure(name: str) -> None:
    """Handle a service failure: increment counter, restart or cooldown."""
    now = time.time()

    # Check if in cooldown
    if now < _cooldown_until[name]:
        remaining = int(_cooldown_until[name] - now)
        log.warning("COOLDOWN %s — %ds remaining (skipping restart)", name, remaining)
        return

    _fail_counts[name] += 1
    log.warning("%s FAILED (consecutive: %d/%d)", name, _fail_counts[name], MAX_CONSECUTIVE_FAILS)

    if _fail_counts[name] >= MAX_CONSECUTIVE_FAILS:
        # Enter cooldown
        _cooldown_until[name] = now + COOLDOWN
        log.critical(
            "CRITICAL: %s failed %d times consecutively. "
            "Entering %ds cooldown. Manual intervention may be needed.",
            name, MAX_CONSECUTIVE_FAILS, COOLDOWN,
        )
        _fail_counts[name] = 0
        return

    _restart_service(name)


def _handle_success(name: str) -> None:
    """Reset failure counter on successful check."""
    if _fail_counts[name] > 0:
        log.info("%s recovered (was at %d consecutive failures)", name, _fail_counts[name])
    _fail_counts[name] = 0


def run_checks() -> dict[str, str]:
    """Run all health checks. Returns status dict."""
    results = {}

    for name, svc in SERVICES.items():
        alive = _http_check(svc["url"])
        results[name] = "OK" if alive else "FAIL"

        if alive:
            _handle_success(name)
        else:
            _handle_failure(name)

    # Model availability check (only if all services are up)
    if all(v == "OK" for v in results.values()):
        models_ok = _check_models()
        results["models"] = "OK" if models_ok else "MISSING"

        if not models_ok:
            # Models missing usually means Open WebUI lost connection to FastAPI
            log.warning("skin1004 models missing — restarting Open WebUI to re-fetch model list")
            _restart_service("openwebui")
    else:
        results["models"] = "SKIP"

    return results


def main():
    log.info("=" * 60)
    log.info("SKIN1004 AI Watchdog started")
    log.info("Check interval: %ds | Cooldown: %ds after %d failures",
             CHECK_INTERVAL, COOLDOWN, MAX_CONSECUTIVE_FAILS)
    log.info("=" * 60)

    # Initial grace period — wait for services to start up
    log.info("Initial grace period: 30s")
    time.sleep(30)

    while True:
        try:
            results = run_checks()
            status_str = " | ".join(f"{k}={v}" for k, v in results.items())
            log.info("CHECK: %s", status_str)
        except Exception as e:
            log.error("watchdog_error: %s", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
