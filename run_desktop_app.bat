@echo off
title Nur Trading Bot - Launcher
echo ============================================================
echo   NUR TRADING BOT - LAUNCHER
echo ============================================================
echo.

cd /d "%~dp0"

echo Activating virtual environment if exists...
if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
) else (
    echo [Info] Using system/Anaconda Python environment.
)

echo Checking and installing requirements...
pip install pystray Pillow uvicorn fastapi pydantic stable-baselines3 gymnasium MetaTrader5 websockets pandas numpy --quiet

echo.
echo Starting Nur Trading Bot Desktop Services...
echo.
python desktop_app.py

pause
