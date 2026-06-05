# desktop_app.py
import sys
import os
from pathlib import Path

# Set up local APPDATA storage directory
APPDATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Nur-Bot"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

# Override environment variables for config BEFORE importing project modules
os.environ["DB_PATH"] = str(APPDATA_DIR / "database" / "nur_trading.db")

# Add the project root to sys.path to resolve imports cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Dynamic desktop discovery and .env auto-initialization
def ensure_env_exists():
    """Ensure a .env file exists. If not, write a safe default template."""
    # Check if .env already exists in executable directory, APPDATA, or workspace root
    exe_env = Path(sys.executable).parent / ".env"
    appdata_env = APPDATA_DIR / ".env"
    dev_env = Path(__file__).resolve().parent / ".env"
    
    if exe_env.exists() or appdata_env.exists() or dev_env.exists():
        return
        
    target_env = appdata_env
    try:
        if getattr(sys, "frozen", False):
            # Test if EXE directory is writeable
            test_file = Path(sys.executable).parent / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            target_env = Path(sys.executable).parent / ".env"
    except Exception:
        pass
        
    default_content = """# ============================================================
# Nur Trading Bot — Environment Configuration
# ============================================================
# Fill in your values. Set PAPER_TRADING=true to test without risk.

# ── Telegram (Optional) ──────────────────────────────────────
# Telegram token from @BotFather
TELEGRAM_TOKEN=
# Comma-separated chat IDs allowed to control the bot
ALLOWED_CHAT_IDS=

# ── Trading Mode ─────────────────────────────────────────────
# Set to true to simulate trades without real orders (Recommended first)
PAPER_TRADING=true

# ── Risk Settings ─────────────────────────────────────────────
RISK_PERCENT=1.0
DAILY_LOSS_LIMIT=-50.0
DAILY_PROFIT_TARGET=100.0
MAX_TRADES_PER_DAY=5
MIN_SCORE_TO_TRADE=70

# ── Strategy ─────────────────────────────────────────────────
SYMBOL=XAUUSD
EMA_PERIOD=200
ATR_PERIOD=14
COOLDOWN_SECONDS=30

# ── MT5 Credentials (Optional) ──────────────────────────────
# If paper trading is false, these credentials are used to connect
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
"""
    try:
        target_env.write_text(default_content, encoding="utf-8")
        
        # Show premium popup message box on Windows
        import ctypes
        welcome_msg = (
            "Welcome to Nur Trading Bot!\n\n"
            f"We have generated a configuration '.env' file for you at:\n{target_env}\n\n"
            "By default, the bot starts in SAFE PAPER TRADING mode. "
            "Please configure your settings and Telegram/MT5 details in this file, then restart the application."
        )
        ctypes.windll.user32.MessageBoxW(0, welcome_msg, "Nur Bot Initialized", 0x40) # MB_ICONINFORMATION
        
        # Open the .env file in default text editor
        os.startfile(str(target_env))
    except Exception as exc:
        pass

# Initialize configuration template if needed before imports load
ensure_env_exists()

# ─── FAST STARTUP: Only import the absolute minimum for the window ─────────
# Heavy imports (config, database, MT5, etc.) are deferred to background threads
import threading
import time
import webview

# Global variables
icon = None
window = None
fastapi_thread = None
bot_thread = None
telegram_thread = None
_logger = None  # Lazy-initialized logger
_services_started = False

# ─── INSTANT SPLASH HTML ──────────────────────────────────────────────────
# This renders immediately in the webview while all backend services boot
SPLASH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nur Trading Bot</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #0a0d14;
    color: #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    overflow: hidden;
  }

  .splash {
    text-align: center;
    animation: fadeIn 0.3s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .logo-ring {
    width: 80px; height: 80px;
    margin: 0 auto 28px;
    border-radius: 50%;
    border: 3px solid transparent;
    border-top-color: #6366f1;
    border-right-color: #8b5cf6;
    animation: spin 1s linear infinite;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .logo-ring::after {
    content: 'N';
    font-size: 28px;
    font-weight: 700;
    color: #6366f1;
    animation: spin-reverse 1s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes spin-reverse { to { transform: rotate(-360deg); } }

  h1 {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
    background: linear-gradient(135deg, #6366f1, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .subtitle {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 32px;
  }

  .status {
    font-size: 12px;
    color: #475569;
    letter-spacing: 0.5px;
  }

  .status .dot {
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #6366f1;
    margin-right: 6px;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.4; transform: scale(0.9); }
    50% { opacity: 1; transform: scale(1.1); }
  }

  .progress-bar {
    width: 200px;
    height: 3px;
    background: #1e293b;
    border-radius: 3px;
    margin: 20px auto 0;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    width: 30%;
    background: linear-gradient(90deg, #6366f1, #a78bfa);
    border-radius: 3px;
    animation: loading 2s ease-in-out infinite;
  }

  @keyframes loading {
    0% { width: 0%; margin-left: 0%; }
    50% { width: 60%; margin-left: 20%; }
    100% { width: 0%; margin-left: 100%; }
  }
</style>
</head>
<body>
  <div class="splash">
    <div class="logo-ring"></div>
    <h1>NUR Trading Bot</h1>
    <p class="subtitle">Initializing trading engine...</p>
    <p class="status"><span class="dot"></span>Starting services</p>
    <div class="progress-bar"><div class="progress-fill"></div></div>
  </div>

  <script>
    // Auto-redirect once FastAPI is ready
    const CHECK_INTERVAL = 300; // ms
    const MAX_WAIT = 30000; // 30s timeout
    let elapsed = 0;

    function checkBackend() {
      fetch('http://127.0.0.1:8000/api/health', { mode: 'cors' })
        .then(r => { if (r.ok) window.location.href = 'http://127.0.0.1:8000/'; })
        .catch(() => {});
      
      elapsed += CHECK_INTERVAL;
      if (elapsed < MAX_WAIT) {
        setTimeout(checkBackend, CHECK_INTERVAL);
      } else {
        document.querySelector('.status').innerHTML = 
          '<span style="color:#ef4444">⚠ Backend taking longer than expected...</span>';
      }
    }

    // Start checking after a brief moment
    setTimeout(checkBackend, 500);
  </script>
</body>
</html>
"""


def _get_logger():
    """Lazy logger initialization — avoids importing the full logging stack at module level."""
    global _logger
    if _logger is None:
        from utils.logger import get_logger
        _logger = get_logger(__name__)
    return _logger


def get_desktop_path():
    """Find the active Desktop folder on Windows dynamically via the Registry, with fallbacks."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        path, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        return Path(os.path.expandvars(path))
    except Exception:
        pass
    
    # Fallback checking OneDrive and default locations
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    if user_profile:
        onedrive_desktop = user_profile / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            return onedrive_desktop
        standard_desktop = user_profile / "Desktop"
        if standard_desktop.exists():
            return standard_desktop
            
    return Path.home() / "Desktop"

def create_desktop_shortcut():
    """Create a shortcut on the user's desktop using native PowerShell (zero-dependency)."""
    try:
        import subprocess
        desktop = get_desktop_path()
        shortcut_path = desktop / "Nur Bot.lnk"
        
        # Always re-create the shortcut to ensure its arguments/working dir are correct
        target_exe = sys.executable
        script_path = Path(__file__).resolve()
        work_dir = script_path.parent
        
        # Powershell command to generate a clean shortcut
        cmd = (
            f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut(\'{shortcut_path}\'); '
            f'$s.TargetPath = \'{target_exe}\'; '
            f'$s.Arguments = \'"{script_path}"\'; '
            f'$s.WorkingDirectory = \'{work_dir}\'; '
            f'$s.Save()'
        )
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
        _get_logger().info(f"Desktop shortcut created successfully at: {shortcut_path}")
    except Exception as exc:
        _get_logger().warning(f"Could not create desktop shortcut: {exc}")

def start_fastapi():
    """Start FastAPI Uvicorn server in a thread."""
    try:
        import uvicorn
        from api.main import app
        config_uvicorn = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
        config_uvicorn.install_signal_handlers = False
        server = uvicorn.Server(config_uvicorn)
        server.run()
    except Exception as exc:
        _get_logger().error(f"FastAPI Server error: {exc}")

def start_bot_engine():
    """Start Bot Engine loop in a thread."""
    try:
        from core.engine import TradingEngine
        engine = TradingEngine()
        engine.run()
    except Exception as exc:
        _get_logger().error(f"Bot Engine error: {exc}")

def start_telegram_bot():
    """Start Telegram bot polling in a thread."""
    try:
        from integrations.telegram_bot import run_telegram
        run_telegram()
    except Exception as exc:
        _get_logger().error(f"Telegram Bot error: {exc}")

def open_dashboard():
    """Show the local dashboard pywebview window."""
    global window
    if window:
        window.show()

def generate_tray_image(color="green"):
    """Draw a status dot image for the system tray (green=running, red=stopped)."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    dot_color = (16, 185, 129, 255) if color == "green" else (239, 68, 68, 255)
    # Draw a smooth round circle representing bot state
    draw.ellipse([8, 8, 56, 56], fill=dot_color)
    return image

def _call_shutdown_api():
    """Call the local /api/shutdown endpoint to trigger clean teardown."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/shutdown",
            method="POST",
            data=b"",
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3)
        _get_logger().info("Shutdown API call successful")
    except Exception as exc:
        _get_logger().warning(f"Shutdown API call failed (fallback to direct): {exc}")
        # Fallback: directly set shared_state flags
        try:
            import shared_state
            import MetaTrader5 as mt5_mod
            shared_state.shutdown = True
            shared_state.bot_running = False
            shared_state.authenticated = False
            try:
                mt5_mod.shutdown()
            except Exception:
                pass
        except Exception:
            pass

def exit_app():
    """Initiate a clean shutdown of all threads and stop the tray icon."""
    _get_logger().info("Shutdown requested. Stopping all services...")

    # Step 1: Call the shutdown API to cleanly stop MT5 + FastAPI
    _call_shutdown_api()

    # Step 2: Set shared_state flags directly as a safety net
    try:
        import shared_state
        shared_state.shutdown = True
        shared_state.bot_running = False
        shared_state.authenticated = False
    except Exception:
        pass

    # Step 3: Wait briefly for background threads to wind down
    time.sleep(1.5)

    # Step 4: Stop the tray icon loop
    if icon:
        try:
            icon.stop()
        except Exception:
            pass

    # Step 5: Force exit the entire process tree
    _get_logger().info("Force exiting process...")
    os._exit(0)

def setup_tray():
    """Initialize pystray System Tray icon with dynamic status updates."""
    global icon
    
    try:
        from pystray import Icon, Menu, MenuItem
    except ImportError:
        _get_logger().warning("pystray not available — skipping tray icon")
        return
    
    def on_open(icon, item):
        open_dashboard()
        
    def on_exit(icon, item):
        exit_app()

    menu = Menu(
        MenuItem("Open Dashboard", on_open, default=True),
        MenuItem("Exit App", on_exit)
    )
    
    icon = Icon(
        "Nur Bot",
        icon=generate_tray_image("green"),
        title="NUR Trading Bot (Active)",
        menu=menu
    )
    
    # Run the icon main loop in a background thread so it doesn't block the main thread
    tray_thread = threading.Thread(target=icon.run, name="tray_icon_thread", daemon=True)
    tray_thread.start()


def _boot_services():
    """
    Background service initializer — runs in a separate thread so the UI
    window appears INSTANTLY while heavy work happens here.
    
    Startup order:
      1. Import config + shared_state (lightweight .env parsing)
      2. Initialize SQLite database (bcrypt hash for default user)
      3. Start FastAPI server (the dashboard needs this first)
      4. Start bot engine (waits for auth anyway — dormant until login)
      5. Start Telegram bot (optional, non-critical)
      6. Setup system tray icon
      7. Create desktop shortcut (PowerShell — deferred to very last)
    """
    global fastapi_thread, bot_thread, telegram_thread, _services_started
    logger = _get_logger()
    
    try:
        # ── Step 1: Core config + state ───────────────────────────
        import config
        import shared_state
        logger.info(f"Initializing at: {APPDATA_DIR}")

        # ── Step 2: Database initialization ───────────────────────
        from database.db import init_db
        init_db(Path(config.DB_PATH))
        
        # ── Step 3: Enable global execution states ────────────────
        shared_state.bot_running = True

        # ── Step 4: Start FastAPI (highest priority — UI needs it) ─
        fastapi_thread = threading.Thread(target=start_fastapi, name="fastapi_backend", daemon=True)
        fastapi_thread.start()
        
        # ── Step 5: Start bot engine (will stay dormant until auth) ─
        bot_thread = threading.Thread(target=start_bot_engine, name="trading_bot_engine", daemon=True)
        bot_thread.start()
        
        # ── Step 6: Start Telegram bot ────────────────────────────
        telegram_thread = threading.Thread(target=start_telegram_bot, name="telegram_bot", daemon=True)
        telegram_thread.start()
        
        # ── Step 7: System tray icon ──────────────────────────────
        setup_tray()
        
        # ── Step 8: Desktop shortcut (lowest priority — deferred) ─
        threading.Thread(target=create_desktop_shortcut, name="shortcut_creator", daemon=True).start()
        
        _services_started = True
        logger.info("All background services initialized successfully")
        
    except Exception as exc:
        logger.error(f"Background service initialization failed: {exc}", exc_info=True)


def main():
    global window

    # ── INSTANT WINDOW: Show splash screen immediately ────────────
    # The window renders in under 1 second while all services boot in background
    window = webview.create_window(
        "Nur Trading Bot Dashboard",
        html=SPLASH_HTML,
        width=1200,
        height=800,
        resizable=True,
        zoomable=True,
        background_color="#0a0d14"
    )
    
    # When the window is actually closed (destroyed), perform full shutdown
    def on_closing():
        _get_logger().info("Window close event detected — initiating full shutdown...")
        # Run exit_app in a thread to avoid blocking the webview close sequence
        threading.Thread(target=exit_app, daemon=True).start()
        return True  # Allow the window to close/destroy
        
    window.events.closing += on_closing

    # ── BACKGROUND BOOT: Start all heavy services in a background thread ──
    boot_thread = threading.Thread(target=_boot_services, name="service_bootstrap", daemon=True)
    boot_thread.start()
    
    # Start webview main loop (this will block the main thread)
    # The splash HTML auto-polls /api/health and redirects once FastAPI is ready
    webview.start(
        storage_path=str(APPDATA_DIR / "webview_cache"),
        private_mode=False
    )

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import ctypes
        import traceback
        err_msg = f"Nur Bot failed to start:\n\n{e}\n\nTraceback:\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        try:
            with open("startup_error.log", "a", encoding="utf-8") as f:
                f.write(err_msg + "\n")
        except Exception:
            pass
        try:
            ctypes.windll.user32.MessageBoxW(0, err_msg, "Nur Bot Startup Error", 0x10) # MB_ICONERROR
        except Exception:
            pass
        sys.exit(1)
