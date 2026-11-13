"""
indicators/rsi.py — RSI(14) calculator. No external deps beyond numpy.
"""
import numpy as np


def calculate_rsi(closes: list[float], period: int = 14) -> float:
    """RSI for the most recent bar. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0

    prices = np.array(closes[-(period + 1):], dtype=float)
    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = gains.mean()
    avg_loss = losses.mean()

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def rsi_score(rsi: float, direction: str) -> tuple[int, str]:
    """
    Returns (score_delta, reason_string).

    BUY ideal zone:      RSI 40-60 → +10
    BUY acceptable dip:  RSI 35-40 → +5
    BUY overbought:      RSI >64   → -20 (exhaustion — do not buy top)
    BUY falling knife:   RSI <35   → -15 (oversold danger)

    SELL ideal pullback: RSI 40-60 → +10
    SELL acceptable:     RSI 60-64 → +5
    SELL oversold:       RSI <36   → -20 (exhaustion — do not short bottom)
    SELL uptrend surge:  RSI >64   → -15 (overbought danger)
    """
    if direction == "BUY":
        if 40 <= rsi <= 60:
            return 10,  f"+10 RSI={rsi:.1f} (ideal BUY zone)"
        elif 35 <= rsi < 40:
            return 5,   f"+5 RSI={rsi:.1f} (acceptable dip)"
        elif rsi > 64:
            return -20, f"-20 RSI={rsi:.1f} (overbought exhaustion)"
        elif rsi < 35:
            return -15, f"-15 RSI={rsi:.1f} (oversold / falling knife)"
        else:
            return 0,   f"+0 RSI={rsi:.1f} (neutral)"
    else:  # SELL
        if 40 <= rsi <= 60:
            return 10,  f"+10 RSI={rsi:.1f} (ideal SELL pullback zone)"
        elif 60 < rsi <= 64:
            return 5,   f"+5 RSI={rsi:.1f} (acceptable bounce)"
        elif rsi < 36:
            return -20, f"-20 RSI={rsi:.1f} (oversold exhaustion — do not short bottom)"
        elif rsi > 64:
            return -15, f"-15 RSI={rsi:.1f} (overbought / uptrend surge)"
        else:
            return 0,   f"+0 RSI={rsi:.1f} (neutral)"
