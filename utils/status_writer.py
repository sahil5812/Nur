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

    STATUS_FILE.parent.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, indent=2))
