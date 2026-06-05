@echo off
echo ========================================
echo   Nur Trading Agent - Setup
echo ========================================
echo.

cd /d "%~dp0"

echo Step 1: Installing Python packages...
pip install -r requirements.txt
pip install MetaTrader5

echo.
echo Step 2: Creating data directory...
if not exist "data" mkdir data

echo.
echo Step 3: Checking for historical data...
if not exist "data\historical_xauusd_m1.csv" (
    echo WARNING: No historical data found!
    echo.
    echo To get data:
    echo 1. Open MT5
    echo 2. Press F2 (History Center)
    echo 3. Select XAUUSD, M1 timeframe
    echo 4. Click Export
    echo 5. Save to: data\historical_xauusd_m1.csv
    echo.
) else (
    echo Found historical data file!
)

echo.
echo Step 4: Testing imports...
python -c "import pandas; import numpy; import MetaTrader5; print('All packages installed successfully!')"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. For backtesting: run run_backtest.bat
echo 2. For live trading: run run_live.bat
echo.
pause

