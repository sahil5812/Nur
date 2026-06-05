@echo off
title NUR - Bot Watchdog
cd /d "C:\Users\Abusahil\OneDrive\Desktop\Nur-main"

echo Watchdog active - monitoring Nur bot...

:: Ensure log directory exists
if not exist logs mkdir logs

:loop
set "RUNNING=0"
set "BOT_PID="
if not exist logs\bot.pid goto restart

set /p BOT_PID=<logs\bot.pid
if "%BOT_PID%"=="" goto restart

tasklist /FI "PID eq %BOT_PID%" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    set "RUNNING=1"
)

if "%RUNNING%"=="1" goto sleep

:restart
set "timestamp=%date% %time%"
echo [%timestamp%] Bot is not running. Starting/Restarting main.py...
echo %timestamp% - Restarting main.py >> logs\watchdog.log
if exist logs\bot.pid del /q logs\bot.pid
if exist .venv\Scripts\activate (
    start "NUR - Bot Engine" cmd /c "call .venv\Scripts\activate && python main.py"
) else if exist venv\Scripts\activate (
    start "NUR - Bot Engine" cmd /c "call venv\Scripts\activate && python main.py"
) else (
    start "NUR - Bot Engine" cmd /c "python main.py"
)
:: Wait 5 seconds to let the bot startup and write its PID
ping -n 6 127.0.0.1 >nul

:sleep
ping -n 31 127.0.0.1 >nul
goto loop

