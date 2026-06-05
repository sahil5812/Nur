"""
intelligence/regime.py — Market regime detector.

Regimes:
  TRENDING        → EMA has slope, ATR normal. Best for our strategy.
  RANGING         → EMA flat, price oscillates. Raise score threshold.
  BREAKOUT        → Price far from EMA, elevated ATR.
  HIGH_VOLATILITY → ATR 2×+ average. Skip trading.
"""
from utils.logger import get_logger

logger = get_logger(__name__)

TRENDING        = "TRENDING"
RANGING         = "RANGING"
BREAKOUT        = "BREAKOUT"
HIGH_VOLATILITY = "HIGH_VOLATILITY"

# Score threshold override per regime (999 = skip)
THRESHOLDS: dict[str, int] = {
    TRENDING:        65,
    RANGING:         85,
    BREAKOUT:        75,
    HIGH_VOLATILITY: 999,
}

LABELS: dict[str, str] = {
    TRENDING:        "📈 TRENDING",
    RANGING:         "↔️  RANGING",
    BREAKOUT:        "💥 BREAKOUT",
    HIGH_VOLATILITY: "⚡ HIGH VOL",
}


def detect_regime(
    closes: list[float],
    ema_history: list[float],
    atr: float,
    atr_history: list[float],
) -> str:
    """Classify current market regime from recent price/EMA/ATR data."""
    if len(closes) < 20 or len(ema_history) < 6:
        return TRENDING

    price    = closes[-1]
    ema_now  = ema_history[-1]
    ema_5ago = ema_history[-6]

    avg_atr      = sum(atr_history) / len(atr_history) if atr_history else atr
    atr_ratio    = atr / avg_atr if avg_atr > 0 else 1.0
    ema_slope    = abs(ema_now - ema_5ago) / ema_5ago * 100 if ema_5ago > 0 else 0
    dist_pct     = abs(price - ema_now) / ema_now * 100 if ema_now > 0 else 0

    if atr_ratio >= 2.0:
        regime = HIGH_VOLATILITY
    elif dist_pct > 0.5 and atr_ratio > 1.3:
        regime = BREAKOUT
    elif ema_slope < 0.01 and dist_pct < 0.15 and atr_ratio < 0.9:
        regime = RANGING
    else:
        regime = TRENDING

    logger.debug(
        f"Regime={regime} atr_ratio={atr_ratio:.2f} "
        f"slope={ema_slope:.4f}% dist={dist_pct:.3f}%"
    )
    return regime


def get_threshold(regime: str, base: int) -> int:
    return THRESHOLDS.get(regime, base)
