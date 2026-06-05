@echo off
echo ============================================================
echo   NUR TRADING PLATFORM - FULL RUNNER
echo ============================================================
echo.
echo Running Auto Database Backup...
if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
) else if exist venv\Scripts\activate (
    call venv\Scripts\activate
)
python scripts/backup_db.py
echo.
echo This script will launch:
echo   1. MetaTrader 5 Client
echo   2. The Bot Watchdog (monitoring main.py)
echo   3. The FastAPI Backend API (port 8000)
echo   4. The Vite React Dashboard UI (port 5173)
echo.
echo Please ensure that:
echo   - Your .env file contains correct ALLOWED_CHAT_IDS and TELEGRAM_TOKEN.
echo.
pause

cd /d "C:\Users\Abusahil\OneDrive\Desktop\Nur-main"
set DB_PATH=C:\NurBot\database\nur_trading.db

echo Starting MetaTrader 5...
start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
ping -n 6 127.0.0.1 >nul
echo.

echo [1/3] Starting Bot Watchdog...
start "NUR - Bot Watchdog" cmd /k "run_bot_watchdog.bat"

echo [2/3] Starting FastAPI Backend API...
if exist .venv\Scripts\activate (
    start "NUR - Dashboard API" cmd /k "call .venv\Scripts\activate && uvicorn api.main:app --reload --port 8000"
) else if exist venv\Scripts\activate (
    start "NUR - Dashboard API" cmd /k "call venv\Scripts\activate && uvicorn api.main:app --reload --port 8000"
) else (
    start "NUR - Dashboard API" cmd /k "uvicorn api.main:app --reload --port 8000"
)

echo [3/3] Starting React Dashboard UI...
start "NUR - Dashboard UI" cmd /k "cd dashboard && npm run dev"

echo.
echo ============================================================
echo   All systems launching in separate terminal windows!
echo ============================================================
echo   - Dashboard API: http://localhost:8000/docs (Swagger Docs)
echo   - Dashboard UI:  http://localhost:5173/ (Main interface)
echo ============================================================
echo.
pause
