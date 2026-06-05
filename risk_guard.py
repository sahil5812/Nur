from database.stats_db import load_stats

def trading_blocked():

    stats = load_stats()

    # daily profit lock
    if stats["today_pnl"] >= 100:
        return True, "DAILY PROFIT TARGET HIT"

    # loss streak pause
    if stats["loss_streak"] >= 3:
        return True, "LOSS STREAK PAUSE"

    return False, ""