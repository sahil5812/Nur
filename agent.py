"""
agent.py — AI scoring agent for Nur Trading Bot.

Phase 2 upgrade: RSI and MACD added as optional scoring factors.
All original scoring logic is UNCHANGED — new factors stack on top.
Backward compatible: rsi/macd params default to neutral if not supplied.
"""
from database.stats_db import load_stats
from indicators.rsi  import rsi_score
from indicators.macd import macd_score


def calculate_score(
    h1_trend_ok: bool,
    pullback_seen: bool,
    atr: float,
    price: float,
    ema: float,
    can_trade: bool,
    # ── Phase 2 additions (optional, neutral defaults) ────────
    rsi: float         = 50.0,
    macd_line: float   = 0.0,
    macd_signal: float = 0.0,
    direction: str     = "BUY",
) -> tuple[int, list[str]]:

    score   = 0
    reasons = []

    # ═══════════════════════════════════════════════════════════
    # ORIGINAL SCORING LOGIC (unchanged)
    # ═══════════════════════════════════════════════════════════

    if h1_trend_ok:
        score += 25
        reasons.append("+25 Trend aligned")

    if pullback_seen:
        score += 20
        reasons.append("+20 Pullback confirmed")

    if atr > 2.0:
        score += 15
        reasons.append("+15 Strong ATR")
    elif atr > 1.2:
        score += 8
        reasons.append("+8 Medium ATR")
    else:
        reasons.append("+0 Weak ATR")

    distance = abs(price - ema)
    if distance > 0.50:
        score += 15
        reasons.append("+15 Clean EMA distance")
    elif distance > 0.25:
        score += 8
        reasons.append("+8 Small EMA distance")

    if can_trade:
        score += 10
        reasons.append("+10 Cooldown ready")

    stats = load_stats()

    if stats["loss_streak"] >= 3:
        score -= 30
        reasons.append("-30 Loss streak 3+")
    elif stats["loss_streak"] == 2:
        score -= 20
        reasons.append("-20 Loss streak 2")
    elif stats["loss_streak"] == 1:
        score -= 10
        reasons.append("-10 Recent loss")

    if stats["win_streak"] >= 3:
        score += 10
        reasons.append("+10 Win streak")

    if stats["today_pnl"] <= -50:
        score -= 40
        reasons.append("-40 Daily loss limit")
    elif stats["today_pnl"] <= -25:
        score -= 20
        reasons.append("-20 Daily PnL weak")

    if stats["today_pnl"] >= 50:
        score += 10
        reasons.append("+10 Strong daily PnL")

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: RSI FILTER
    # Only applied when caller passes a real RSI value (not 50.0 default)
    # ═══════════════════════════════════════════════════════════
    if rsi != 50.0:
        delta, label = rsi_score(rsi, direction)
        score += delta
        reasons.append(label)

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: MACD CONFIRMATION
    # Only applied when caller passes real MACD values
    # ═══════════════════════════════════════════════════════════
    if macd_line != 0.0 or macd_signal != 0.0:
        delta, label = macd_score(macd_line, macd_signal, direction)
        score += delta
        reasons.append(label)

    # ═══════════════════════════════════════════════════════════
    # CLAMP
    # ═══════════════════════════════════════════════════════════
    score = max(0, min(100, score))
    return score, reasons