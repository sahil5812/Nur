"""
utils/mt5_connector.py — MT5 auto-reconnect with exponential backoff.

Why this matters:
  MT5 can disconnect due to server maintenance, weekend downtime, or network
  blips. Without auto-reconnect, the bot silently stops trading with no alert.

How it works:
  ensure_connected() is called at the TOP of every main loop iteration.
  If MT5 is healthy → returns True immediately (negligible overhead).
  If disconnected  → attempts reconnect with delays: 1s, 2s, 4s ... 60s max.
  On failure       → sends Telegram alert and returns False (bot skips the tick).
  On recovery      → sends Telegram alert and resumes normally.
"""

import time
import MetaTrader5 as mt5

from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_DELAY  = 1    # seconds — first retry delay
_MAX_DELAY   = 60   # seconds — cap for exponential backoff
_MAX_RETRIES = 12   # ~2 minutes total before giving up


def _send_telegram(text: str) -> None:
    """Best-effort Telegram alert. Never raises."""
    try:
        import shared_state
        if shared_state.send_message:
            shared_state.send_message(text)
    except Exception:
        pass


def _is_healthy() -> bool:
    """Fast check — terminal_info() is None when MT5 is disconnected."""
    return mt5.terminal_info() is not None


def connect_mt5() -> bool:
    """
    Attempt a single fresh MT5 connection.
    Shuts down first to clear any stale state.
    """
    mt5.shutdown()
    
    import config
    init_kwargs = {}
    if hasattr(config, "MT5_PATH") and config.MT5_PATH:
        init_kwargs["path"] = config.MT5_PATH
    if hasattr(config, "MT5_LOGIN") and config.MT5_LOGIN:
        init_kwargs["login"] = config.MT5_LOGIN
    if hasattr(config, "MT5_PASSWORD") and config.MT5_PASSWORD:
        init_kwargs["password"] = config.MT5_PASSWORD
    if hasattr(config, "MT5_SERVER") and config.MT5_SERVER:
        init_kwargs["server"] = config.MT5_SERVER

    if mt5.initialize(**init_kwargs):
        logger.info("MT5 connected successfully")
        return True
    logger.error(f"MT5 initialize() failed — {mt5.last_error()}")
    return False


def ensure_connected() -> bool:
    """
    Guarantee MT5 is connected before each loop tick.

    Returns:
        True  — MT5 is ready
        False — all retries exhausted (caller should skip the tick gracefully)
    """
    if _is_healthy():
        return True

    logger.warning("MT5 disconnected — starting reconnect sequence")
    _send_telegram("⚠️ MT5 disconnected — attempting reconnect...")

    delay = _BASE_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        logger.info(f"Reconnect attempt {attempt}/{_MAX_RETRIES} (waiting {delay}s)")
        time.sleep(delay)

        if connect_mt5():
            logger.info(f"MT5 reconnected on attempt {attempt}")
            _send_telegram("✅ MT5 reconnected — trading resumed")
            return True

        delay = min(delay * 2, _MAX_DELAY)

    logger.critical("MT5 reconnection failed after all retries — bot cannot continue")
    _send_telegram("🚨 CRITICAL: MT5 reconnection failed — bot halted. Manual restart required.")
    return False
