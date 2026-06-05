import json
from pathlib import Path
from datetime import datetime

STATS_FILE = Path("stats.json")


# ==================================================
# DEFAULT
# ==================================================
def default_stats():
    return {
        "total_trades": 0,
        "today_trades": 0,

        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,

        "total_pnl": 0.0,
        "today_pnl": 0.0,

        "best_win": 0.0,
        "worst_loss": 0.0,

        "win_streak": 0,
        "loss_streak": 0,

        "max_win_streak": 0,
        "max_loss_streak": 0,

        "avg_win": 0.0,
        "avg_loss": 0.0,

        "gross_win": 0.0,
        "gross_loss": 0.0,

        "trading_locked": False,

        "last_reset_day": str(datetime.now().date())
    }


# ==================================================
# SAVE
# ==================================================
def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=4)


# ==================================================
# LOAD
# ==================================================
def load_stats():

    if not STATS_FILE.exists():
        stats = default_stats()
        save_stats(stats)
        return stats

    with open(STATS_FILE, "r") as f:
        stats = json.load(f)

    today = str(datetime.now().date())

    # ================= DAILY RESET =================
    if stats["last_reset_day"] != today:

        stats["today_pnl"] = 0.0
        stats["today_trades"] = 0

        stats["trading_locked"] = False

        stats["win_streak"] = 0
        stats["loss_streak"] = 0

        stats["last_reset_day"] = today

        save_stats(stats)

    return stats


# ==================================================
# UPDATE AFTER TRADE CLOSE
# ==================================================
def update_stats(pnl):

    stats = load_stats()

    stats["total_trades"] += 1
    stats["today_trades"] += 1

    stats["total_pnl"] += pnl
    stats["today_pnl"] += pnl

    # ================= WIN =================
    if pnl > 0:

        stats["wins"] += 1
        stats["gross_win"] += pnl

        stats["win_streak"] += 1
        stats["loss_streak"] = 0

        if pnl > stats["best_win"]:
            stats["best_win"] = pnl

    # ================= LOSS =================
    else:

        stats["losses"] += 1
        stats["gross_loss"] += abs(pnl)

        stats["loss_streak"] += 1
        stats["win_streak"] = 0

        if pnl < stats["worst_loss"]:
            stats["worst_loss"] = pnl

    # ================= STREAK RECORDS =================
    if stats["win_streak"] > stats["max_win_streak"]:
        stats["max_win_streak"] = stats["win_streak"]

    if stats["loss_streak"] > stats["max_loss_streak"]:
        stats["max_loss_streak"] = stats["loss_streak"]

    # ================= WIN RATE =================
    if stats["total_trades"] > 0:
        stats["win_rate"] = round(
            stats["wins"] / stats["total_trades"] * 100, 2
        )

    # ================= AVERAGES =================
    if stats["wins"] > 0:
        stats["avg_win"] = round(
            stats["gross_win"] / stats["wins"], 2
        )

    if stats["losses"] > 0:
        stats["avg_loss"] = round(
            stats["gross_loss"] / stats["losses"], 2
        )

    save_stats(stats)


# ==================================================
# DAILY LOSS LOCK
# ==================================================
def check_daily_lock(limit=-50.0):

    stats = load_stats()

    if stats["today_pnl"] <= limit:
        stats["trading_locked"] = True
        save_stats(stats)
        return True

    return stats["trading_locked"]


# ==================================================
# DAILY PROFIT LOCK
# ==================================================
def check_profit_lock(target=100.0):

    stats = load_stats()

    if stats["today_pnl"] >= target:
        stats["trading_locked"] = True
        save_stats(stats)
        return True

    return False