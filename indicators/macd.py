"""
indicators/macd.py — MACD(12,26,9) calculator. No external deps.
"""


def _ema_series(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def calculate_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """
    Returns (macd_line, signal_line, histogram) for the most recent bar.
    Returns (0, 0, 0) if insufficient data.
    """
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0

    fast_ema  = _ema_series(closes, fast)
    slow_ema  = _ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]

    if len(macd_line) < signal_period:
        return round(macd_line[-1], 5), 0.0, round(macd_line[-1], 5)

    signal_line = _ema_series(macd_line, signal_period)
    m = round(macd_line[-1],   5)
    s = round(signal_line[-1], 5)
    return m, s, round(m - s, 5)


def macd_score(macd: float, signal: float, direction: str) -> tuple[int, str]:
    """
    BUY:  MACD > signal → momentum aligned → +10, else -10
    SELL: MACD < signal → momentum aligned → +10, else -10
    """
    if direction == "BUY":
        if macd > signal:
            return 10,  f"+10 MACD bullish (macd={macd:.4f} > sig={signal:.4f})"
        else:
            return -10, f"-10 MACD bearish — counter-trend BUY"
    else:
        if macd < signal:
            return 10,  f"+10 MACD bearish (macd={macd:.4f} < sig={signal:.4f})"
        else:
            return -10, f"-10 MACD bullish — counter-trend SELL"
