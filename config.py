"""
config.py — Centralized typed configuration for Nur Trading Bot.

ALL settings and secrets are loaded from .env via python-dotenv.
Every other module imports from here — no scattered magic numbers,
no hardcoded credentials anywhere else in the codebase.

Usage:
    from config import settings
    print(settings.SYMBOL)
"""

from pathlib import Path
from dotenv import load_dotenv
import os

import sys

# Load .env from multiple potential locations:
# 1. Next to the executable (if frozen)
# 2. Inside %APPDATA%/Nur-Bot/
# 3. Inside the same directory as this file (development)
paths_to_try = []
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).parent
    paths_to_try.append(exe_dir / ".env")
    
    appdata_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "Nur-Bot"
    paths_to_try.append(appdata_dir / ".env")

paths_to_try.append(Path(__file__).parent / ".env")

loaded = False
for path in paths_to_try:
    if path.exists():
        load_dotenv(path)
        _ENV_PATH = path
        loaded = True
        break

if not loaded:
    _ENV_PATH = Path(__file__).parent / ".env"  # fallback


def _require(key: str) -> str:
    """Get a required env variable or raise a descriptive error."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"\n❌ Required environment variable '{key}' is missing or empty.\n"
            f"   Check your .env file at: {_ENV_PATH}\n"
            f"   Copy .env.example → .env and fill in your values."
        )
    return value


def _get(key: str, default: str) -> str:
    return os.getenv(key, default).strip()


# ─────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "").strip()

_raw_ids = _get("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: set[int] = {
    int(cid.strip())
    for cid in _raw_ids.split(",")
    if cid.strip().lstrip("-").isdigit()
}

# ─────────────────────────────────────────────
# Trading Mode
# ─────────────────────────────────────────────
PAPER_TRADING: bool = _get("PAPER_TRADING", "false").lower() == "true"

# ─────────────────────────────────────────────
# Risk Settings
# ─────────────────────────────────────────────
RISK_PERCENT: float      = float(_get("RISK_PERCENT",         "1.0"))
DAILY_LOSS_LIMIT: float  = float(_get("DAILY_LOSS_LIMIT",     "-50.0"))
DAILY_PROFIT_TARGET: float = float(_get("DAILY_PROFIT_TARGET", "100.0"))
MAX_TRADES_PER_DAY: int  = int(_get("MAX_TRADES_PER_DAY",     "5"))
MIN_SCORE_TO_TRADE: int  = int(_get("MIN_SCORE_TO_TRADE",     "70"))

# ─────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────
SYMBOL: str         = _get("SYMBOL",          "XAUUSD")
EMA_PERIOD: int     = int(_get("EMA_PERIOD",   "200"))
ATR_PERIOD: int     = int(_get("ATR_PERIOD",   "14"))
COOLDOWN_SECONDS: int = int(_get("COOLDOWN_SECONDS", "30"))

# ─────────────────────────────────────────────
# MT5 Login Credentials (Optional)
# ─────────────────────────────────────────────
MT5_LOGIN: int | None = int(os.getenv("MT5_LOGIN", "0")) if os.getenv("MT5_LOGIN") else None
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "")
MT5_PATH: str = os.getenv("MT5_PATH", "")

# ─────────────────────────────────────────────
# Paths (derived — not in .env)
# ─────────────────────────────────────────────
BASE_DIR: Path  = Path(__file__).parent
LOG_DIR: Path   = BASE_DIR / "logs"
_default_appdata = Path(os.environ.get("APPDATA", str(Path.home()))) / "Nur-Bot"
DB_PATH: Path   = Path(os.getenv("DB_PATH", str(_default_appdata / "database" / "nur_trading.db")))

# ─────────────────────────────────────────────
# Cloud Database Override (PostgreSQL)
# Set DATABASE_URL to switch from SQLite to PostgreSQL.
# Formats:
#   Supabase:  postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
#   Neon:      postgresql://[USER]:[PASSWORD]@[HOST]/[DB]?sslmode=require
# If unset, the bot uses local SQLite at DB_PATH.
# ─────────────────────────────────────────────
DATABASE_URL: str | None = os.getenv("DATABASE_URL", None)

