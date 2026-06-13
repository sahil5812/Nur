"""
database/stats_db.py — SQLite-backed drop-in replacement for stats.py.

Provides IDENTICAL function signatures to the original stats.py so that
bot_engine.py, agent.py only need their import line changed — zero logic changes.

Public API (same as stats.py):
    load_stats()               → dict
    save_stats(stats)          → None   (kept for compatibility, prefer update_stats)
    update_stats(pnl)          → None
    check_daily_lock(limit)    → bool
    check_profit_lock(target)  → bool

Additional API (new):
    log_trade(...)             → None   (write full trade record to trades table)
"""

from datetime import datetime
from typing import Any

from database.db import get_connection, query_one
from utils.logger import get_logger

logger = get_logger(__name__)

# ─── Internal helpers ─────────────────────────────────────────


def _row_to_dict(row) -> dict[str, Any]:
    """Convert sqlite3.Row → plain dict matching the old stats.json structure."""
    if row is None:
        return default_stats()
    d = dict(row)
    d["trading_locked"] = bool(d["trading_locked"])
    return d


def _today() -> str:
    return str(datetime.now().date())


# ─── Public API ───────────────────────────────────────────────


def default_stats() -> dict[str, Any]:
    """Return a fresh stats dict. Mirrors original stats.py structure exactly."""
    return {
        "total_trades":    0,
        "today_trades":    0,
        "wins":            0,
        "losses":          0,
        "win_rate":        0.0,
        "total_pnl":       0.0,
        "today_pnl":       0.0,
        "best_win":        0.0,
        "worst_loss":      0.0,
        "win_streak":      0,
        "loss_streak":     0,
        "max_win_streak":  0,
        "max_loss_streak": 0,
        "avg_win":         0.0,
        "avg_loss":        0.0,
        "gross_win":       0.0,
        "gross_loss":      0.0,
        "trading_locked":  False,
        "last_reset_day":  str(datetime.now().date()),
        "loss_lock_timestamp": None,
    }


def load_stats(user_id: int = 1) -> dict[str, Any]:
    """
    Load current stats from SQLite for a specific user_id. Handles daily reset automatically.
    Thread-safe read (WAL mode allows concurrent reads).
    """
    row = query_one("SELECT * FROM bot_stats WHERE user_id = ?", (user_id,))
    stats = _row_to_dict(row)
    today = _today()

    # ── Daily reset logic (same as original stats.py) ──────────
    if stats["last_reset_day"] != today:
        stats["today_pnl"]      = 0.0
        stats["today_trades"]   = 0
        stats["trading_locked"] = False
        stats["win_streak"]     = 0
        stats["loss_streak"]    = 0
        stats["last_reset_day"] = today
        stats["loss_lock_timestamp"] = None
        save_stats(stats, user_id=user_id)
        logger.info(f"Daily stats reset for user {user_id} on {today}")

    # ── Time-based lock expiry (LOSS_LOCK_EXPIRE_HOURS) ────────
    if stats["trading_locked"] and stats.get("loss_lock_timestamp"):
        try:
            lock_time = datetime.fromisoformat(stats["loss_lock_timestamp"])
            elapsed_hours = (datetime.now() - lock_time).total_seconds() / 3600.0
            from bot_engine import LOSS_LOCK_EXPIRE_HOURS
            if elapsed_hours >= LOSS_LOCK_EXPIRE_HOURS:
                stats["trading_locked"] = False
                stats["loss_lock_timestamp"] = None
                save_stats(stats, user_id=user_id)
                logger.info(f"Loss lock expired for user {user_id} after {elapsed_hours:.1f}h — trading unlocked")
        except Exception as e:
            logger.warning(f"Failed to check loss lock expiry: {e}")

    return stats


def save_stats(stats: dict[str, Any], user_id: int = 1) -> None:
    """
    Persist the full stats dict atomically for a specific user_id.
    Uses INSERT OR REPLACE to guarantee the row stays consistent.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO bot_stats (
                user_id, total_trades, today_trades, wins, losses, win_rate,
                total_pnl, today_pnl, best_win, worst_loss,
                win_streak, loss_streak, max_win_streak, max_loss_streak,
                avg_win, avg_loss, gross_win, gross_loss,
                trading_locked, last_reset_day, loss_lock_timestamp
            ) VALUES (
                :user_id, :total_trades, :today_trades, :wins, :losses, :win_rate,
                :total_pnl, :today_pnl, :best_win, :worst_loss,
                :win_streak, :loss_streak, :max_win_streak, :max_loss_streak,
                :avg_win, :avg_loss, :gross_win, :gross_loss,
                :trading_locked, :last_reset_day, :loss_lock_timestamp
            )
        """, {**stats, "user_id": user_id, "trading_locked": int(stats["trading_locked"])})


def update_stats(pnl: float, user_id: int = 1) -> None:
    """
    Update stats after a trade closes. Mirrors original stats.py logic exactly.
    Reads, updates, then writes atomically inside a single connection.
    """
    stats = load_stats(user_id=user_id)

    stats["total_trades"] += 1
    stats["today_trades"] += 1
    stats["total_pnl"]    += pnl
    stats["today_pnl"]    += pnl

    if pnl > 0:
        stats["wins"]       += 1
        stats["gross_win"]  += pnl
        stats["win_streak"] += 1
        stats["loss_streak"] = 0
        if pnl > stats["best_win"]:
            stats["best_win"] = pnl
    else:
        stats["losses"]      += 1
        stats["gross_loss"]  += abs(pnl)
        stats["loss_streak"] += 1
        stats["win_streak"]   = 0
        if pnl < stats["worst_loss"]:
            stats["worst_loss"] = pnl

    if stats["win_streak"]  > stats["max_win_streak"]:
        stats["max_win_streak"]  = stats["win_streak"]
    if stats["loss_streak"] > stats["max_loss_streak"]:
        stats["max_loss_streak"] = stats["loss_streak"]

    if stats["total_trades"] > 0:
        stats["win_rate"] = round(stats["wins"] / stats["total_trades"] * 100, 2)
    if stats["wins"]   > 0:
        stats["avg_win"]  = round(stats["gross_win"]  / stats["wins"],   2)
    if stats["losses"] > 0:
        stats["avg_loss"] = round(stats["gross_loss"] / stats["losses"],  2)

    save_stats(stats, user_id=user_id)
    logger.info(
        f"Stats updated for user {user_id} | PnL={pnl:+.2f} | "
        f"Today={stats['today_pnl']:.2f} | "
        f"W/L={stats['wins']}/{stats['losses']}"
    )


def check_daily_lock(limit: float = -50.0, user_id: int = 1) -> bool:
    """Lock trading if today's PnL has hit the loss limit. Mirrors stats.py."""
    stats = load_stats(user_id=user_id)
    if stats["today_pnl"] <= limit:
        if not stats["trading_locked"]:
            stats["trading_locked"] = True
            stats["loss_lock_timestamp"] = datetime.now().isoformat()
            save_stats(stats, user_id=user_id)
            logger.warning(f"Daily loss lock triggered for user {user_id} — today_pnl={stats['today_pnl']:.2f}")
        return True
    return stats["trading_locked"]


def check_profit_lock(target: float = 100.0, user_id: int = 1) -> bool:
    """Lock trading if today's profit target is reached. Mirrors stats.py."""
    stats = load_stats(user_id=user_id)
    if stats["today_pnl"] >= target:
        if not stats["trading_locked"]:
            stats["trading_locked"] = True
            save_stats(stats, user_id=user_id)
            logger.info(f"Daily profit lock triggered for user {user_id} — today_pnl={stats['today_pnl']:.2f}")
        return True
    return False


def log_trade(
    direction: str,
    entry_price: float,
    exit_price: float,
    sl: float,
    lot: float,
    score: int,
    pnl: float,
    exit_reason: str,
    entry_time: str,
    exit_time: str,
    is_paper: bool = False,
    trade_id: str | None = None,
    session: str | None = None,
    user_id: int = 1,
) -> None:
    """
    Write a completed trade record to the trades table.
    This is NEW — the original stats.py had no per-trade history.
    Enables Phase 2 analytics (win rate by session, ATR zone, etc.).
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO trades (
                user_id, trade_id, direction, entry_price, exit_price,
                sl, lot, score, pnl, exit_reason,
                is_paper, entry_time, exit_time, session
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, trade_id, direction, entry_price, exit_price,
            sl, lot, score, pnl, exit_reason,
            int(is_paper), entry_time, exit_time, session,
        ))
    logger.debug(f"Trade logged for user {user_id}: {direction} {pnl:+.2f} [{exit_reason}]")
