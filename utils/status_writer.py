import json
from pathlib import Path
from datetime import datetime

STATUS_FILE = Path("logs/engine_status.json")

def write_status(
    market: str,
    state: str,
    ema200,
    timestamp=None,
    trend: str | None = None,
    last_close: float | None = None,
    rf_prob: float | None = None,
    rf_approved: bool | None = None,
    h4_bias: str | None = None,
    h1_trend: str | None = None,
    regime: str | None = None,
    z_m1: float | None = None,
    rsi: float | None = None,
    atr: float | None = None,
    spread: float | None = None,
    today_trades: int | None = None,
    max_daily_trades: int | None = None,
    limit_reached: bool | None = None,
    cooldown_left: int | None = None,
    reset_seconds_left: int | None = None,
    reset_time_str: str | None = None,
    **extra,
):
    payload = {
        "market": market,
        "state": state,
        "ema200": None if ema200 is None else round(float(ema200), 2),
        "timestamp": timestamp or datetime.utcnow().isoformat(),
    }
    if trend is not None:
        payload["trend"] = trend
    if last_close is not None:
        payload["last_close"] = round(float(last_close), 2)
    if rf_prob is not None:
        payload["rf_prob"] = round(float(rf_prob), 4)
    if rf_approved is not None:
        payload["rf_approved"] = bool(rf_approved)
    if h4_bias is not None:
        payload["h4_bias"] = str(h4_bias)
    if h1_trend is not None:
        payload["h1_trend"] = str(h1_trend)
    if regime is not None:
        payload["regime"] = str(regime)
    if z_m1 is not None:
        payload["z_m1"] = round(float(z_m1), 2)
    if rsi is not None:
        payload["rsi"] = round(float(rsi), 1)
    if atr is not None:
        payload["atr"] = round(float(atr), 2)
    if spread is not None:
        payload["spread"] = round(float(spread), 2)
    if today_trades is not None:
        payload["today_trades"] = int(today_trades)
    if max_daily_trades is not None:
        payload["max_daily_trades"] = int(max_daily_trades)
    if limit_reached is not None:
        payload["limit_reached"] = bool(limit_reached)
    if cooldown_left is not None:
        payload["cooldown_left"] = max(0, int(cooldown_left))
    if reset_seconds_left is not None:
        payload["reset_seconds_left"] = max(0, int(reset_seconds_left))
    if reset_time_str is not None:
        payload["reset_time_str"] = str(reset_time_str)
    for k, v in extra.items():
        if v is not None:
            payload[k] = v

    STATUS_FILE.parent.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, indent=2))
