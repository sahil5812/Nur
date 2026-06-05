@echo off
echo ========================================
echo   Nur Trading Agent - Backtest Runner
echo ========================================
echo.

cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt
pip install MetaTrader5

echo.
echo Starting backtest...
echo.

python backtest/engine_fixed.py

pause

