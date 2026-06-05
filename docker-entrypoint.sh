#!/bin/bash
# ============================================================
# docker-entrypoint.sh — Nur Trading Bot Container Entry Point
# Starts Xvfb virtual display, then launches the requested service
# ============================================================
set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  NUR TRADING BOT — Container Starting        ║"
echo "╚══════════════════════════════════════════════╝"

# ── Start Virtual Display (required for MT5 terminal) ────────
echo "[INIT] Starting Xvfb virtual display on :99..."
Xvfb :99 -screen 0 1024x768x16 &
sleep 2
echo "[INIT] Xvfb started successfully"

# ── Initialize Wine prefix (first run only) ───────────────────
if [ ! -d "$HOME/.wine" ]; then
    echo "[INIT] Initializing Wine prefix (first run)..."
    wineboot --init 2>/dev/null || true
    sleep 3
    echo "[INIT] Wine prefix initialized"
fi

# ── Route to correct service ─────────────────────────────────
SERVICE="${SERVICE_MODE:-bot}"

case "$SERVICE" in
    bot)
        echo "[RUN] Starting Bot Engine (main.py)..."
        exec python -X utf8 main.py
        ;;
    api)
        echo "[RUN] Starting FastAPI Dashboard (run_api.py)..."
        exec python -X utf8 run_api.py
        ;;
    both)
        echo "[RUN] Starting Bot Engine + API Dashboard..."
        python -X utf8 run_api.py &
        API_PID=$!
        echo "[RUN] API started (PID: $API_PID)"
        sleep 2
        exec python -X utf8 main.py
        ;;
    *)
        echo "[ERROR] Unknown SERVICE_MODE: $SERVICE"
        echo "  Valid options: bot, api, both"
        exit 1
        ;;
esac
