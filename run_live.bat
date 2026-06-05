@echo off
echo ========================================
echo   Nur Trading Agent - Live Trading
echo ========================================
echo.
echo WARNING: This will connect to MT5 and execute trades!
echo Make sure you're using a DEMO account.
echo.
pause

cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt
pip install MetaTrader5

echo.
echo Checking MT5 connection...
python -c "import MetaTrader5 as mt5; print('MT5 available:', mt5.initialize())"

echo.
echo Starting live trading...
echo Press CTRL+C to stop
echo.

python main.py

pause

