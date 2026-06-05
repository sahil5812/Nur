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

    BUY ideal zone: RSI 40-65 → +10
    BUY overbought: RSI >75   → -15
    SELL ideal zone: RSI 35-60 → +10
    SELL oversold:   RSI <25   → -15
    """
    if direction == "BUY":
        if 40 <= rsi <= 65:
            return 10,  f"+10 RSI={rsi:.1f} (ideal BUY zone)"
        elif 30 <= rsi < 40 or 65 < rsi <= 75:
            return 5,   f"+5 RSI={rsi:.1f} (acceptable)"
        elif rsi > 75:
            return -15, f"-15 RSI={rsi:.1f} (overbought)"
        else:
            return 5,   f"+5 RSI={rsi:.1f} (oversold bounce)"
    else:  # SELL
        if 35 <= rsi <= 60:
            return 10,  f"+10 RSI={rsi:.1f} (ideal SELL zone)"
        elif 25 <= rsi < 35 or 60 < rsi <= 70:
            return 5,   f"+5 RSI={rsi:.1f} (acceptable)"
        elif rsi < 25:
            return -15, f"-15 RSI={rsi:.1f} (oversold)"
        else:
            return 5,   f"+5 RSI={rsi:.1f} (overbought reversal)"
