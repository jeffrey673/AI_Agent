@echo off
setlocal EnableDelayedExpansion
title SKIN1004 AI — All Servers
cd /d C:\Users\DB_PC\Desktop\python_bcj\AI_Agent

echo ============================================================
echo   SKIN1004 AI — Starting All Servers
echo ============================================================
echo.
echo   [1] FastAPI Backend : http://localhost:8100
echo   [2] Open WebUI      : http://localhost:8080 (internal)
echo   [3] Reverse Proxy   : http://localhost:3000 (user-facing)
echo   [4] Watchdog        : background health monitor
echo.

:: ── 0. Kill stale processes on ports 8080 / 8100 / 3000 ────
echo [0/4] Cleaning up stale processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8100 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak > nul

:: Create logs directory if needed
if not exist logs mkdir logs

:: ── 1. FastAPI AI Backend (port 8100) — start FIRST ────────
echo [1/4] Starting FastAPI Backend on port 8100...
start "FastAPI AI (8100)" cmd /k "cd /d C:\Users\DB_PC\Desktop\python_bcj\AI_Agent && python -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload"

:: Wait for FastAPI /health to respond (max 60s)
echo       Waiting for FastAPI health check...
python _healthcheck.py http://localhost:8100/health 60
if !errorlevel! == 0 (
    echo       FastAPI is ready!
) else (
    echo       WARNING: FastAPI did not respond within 60s, continuing anyway...
)

:: ── 2. Open WebUI (internal, port 8080) — start AFTER FastAPI ──
echo [2/4] Starting Open WebUI on port 8080...
start "Open WebUI (8080)" cmd /k "cd /d C:\Users\DB_PC\Desktop\python_bcj\AI_Agent && set DATA_DIR=C:\Users\DB_PC\.open-webui\data && set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && set ENABLE_VERSION_UPDATE_CHECK=false && set OPENAI_API_BASE_URLS=http://localhost:8100/v1 && set OPENAI_API_KEYS=sk-skin1004 && open-webui serve --port 8080"

:: Wait for Open WebUI to respond (max 90s — Open WebUI is slower)
echo       Waiting for Open WebUI...
python _healthcheck.py http://localhost:8080 90
if !errorlevel! == 0 (
    echo       Open WebUI is ready!
) else (
    echo       WARNING: Open WebUI did not respond within 90s, continuing anyway...
)

:: ── 3. Reverse Proxy (port 3000, user-facing) ─────────────
echo [3/4] Starting Reverse Proxy on port 3000...
start "Proxy (3000)" cmd /k "cd /d C:\Users\DB_PC\Desktop\python_bcj\AI_Agent && python -X utf8 proxy.py"

:: ── 4. Watchdog (background health monitor) ───────────────
echo [4/4] Starting Watchdog monitor...
start "Watchdog" /min cmd /k "cd /d C:\Users\DB_PC\Desktop\python_bcj\AI_Agent && python -X utf8 watchdog.py"

echo.
echo ============================================================
echo   All servers started!
echo   Open http://localhost:3000 in your browser
echo   Watchdog monitoring every 60 seconds
echo ============================================================
echo.
endlocal
