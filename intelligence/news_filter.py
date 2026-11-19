"""
intelligence/news_filter.py — High-impact news blackout window checker.

Combines:
  1. Live ForexFactory High-Impact USD Economic Calendar feed with local file cache.
  2. Deterministic schedule fallbacks (NFP first Friday, CPI second Tuesday, FOMC meetings).

Blocks trading 15–30 min before and after high-impact volatility events.
XAUUSD moves 200–500 pips on these events — never trade blindly through them.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import urllib.request
from utils.logger import get_logger

logger = get_logger(__name__)

BUFFER_MINUTES = 15  # Default 15-minute buffer before & after news

# Local cache path for weekly news calendar
_CACHE_PATH = Path(__file__).resolve().parent.parent / "logs" / "news_calendar.json"
_CACHE_TTL_HOURS = 6

# FOMC dates 2025-2026 (year, month, day) — decision at ~18:00 UTC
_FOMC = {
    (2025, 1, 29), (2025, 3, 19), (2025, 5, 7), (2025, 6, 18),
    (2025, 7, 30), (2025, 9, 17), (2025, 10, 29), (2025, 12, 10),
    (2026, 1, 28), (2026, 3, 18), (2026, 4, 29), (2026, 6, 17),
    (2026, 7, 29), (2026, 9, 16), (2026, 10, 28), (2026, 12, 9),
}


def _first_friday(year: int, month: int) -> int:
    for day in range(1, 8):
        if datetime(year, month, day).weekday() == 4:
            return day
    return 7


def _second_tuesday(year: int, month: int) -> int | None:
    tues = [d for d in range(1, 32)
            if _safe_weekday(year, month, d) == 1]
    return tues[1] if len(tues) >= 2 else None


def _safe_weekday(y, m, d):
    try:
        return datetime(y, m, d).weekday()
    except ValueError:
        return -1


def _within(now: datetime, event: datetime, buffer_minutes: int = BUFFER_MINUTES) -> bool:
    return abs((now - event).total_seconds()) / 60 <= buffer_minutes


def fetch_live_calendar(force: bool = False) -> list[dict]:
    """
    Fetches the weekly ForexFactory economic calendar JSON feed.
    Caches to disk with a 6-hour TTL to prevent network overhead.
    Returns a list of high-impact USD events.
    """
    try:
        if not force and _CACHE_PATH.exists():
            mtime = datetime.fromtimestamp(_CACHE_PATH.stat().st_mtime, tz=timezone.utc)
            if (datetime.now(timezone.utc) - mtime) < timedelta(hours=_CACHE_TTL_HOURS):
                raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
                return raw.get("events", [])
    except Exception as exc:
        logger.debug(f"Error reading news cache: {exc}")

    # Fetch live from official endpoint
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NurBot/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            high_impact_usd = []
            for item in data:
                if item.get("country") == "USD" and item.get("impact") in ("High", "Holiday"):
                    high_impact_usd.append({
                        "title": item.get("title", "High-Impact USD News"),
                        "date": item.get("date"),
                        "impact": item.get("impact"),
                    })

            # Save to cache
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_PATH.write_text(json.dumps({
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "events": high_impact_usd,
            }, indent=2), encoding="utf-8")
            logger.info(f"📰 Live economic calendar updated: {len(high_impact_usd)} USD high-impact events loaded")
            return high_impact_usd
    except Exception as exc:
        logger.warning(f"Live economic calendar fetch bypassed: {exc} — using deterministic fallback")
        if _CACHE_PATH.exists():
            try:
                raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
                return raw.get("events", [])
            except Exception:
                pass
        return []


def is_news_window(now: datetime | None = None, buffer_minutes: int = BUFFER_MINUTES) -> tuple[bool, str]:
    """
    Returns (True, event_name) if inside a news blackout window, else (False, "").
    Checks both deterministic macro schedules (NFP, FOMC, CPI) and live economic calendar.
    """
    is_live_tick = (now is None)
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Deterministic Schedules (always active, guaranteed offline)
    # NFP: 1st Friday each month, 13:30 UTC
    nfp_day = _first_friday(now.year, now.month)
    nfp_time = datetime(now.year, now.month, nfp_day, 13, 30, tzinfo=timezone.utc)
    if _within(now, nfp_time, buffer_minutes):
        return True, f"NFP ({nfp_time.strftime('%H:%M')} UTC)"

    # FOMC: meetings at ~18:00 UTC
    for (y, mo, d) in _FOMC:
        t = datetime(y, mo, d, 18, 0, tzinfo=timezone.utc)
        if _within(now, t, buffer_minutes):
            return True, f"FOMC ({t.strftime('%Y-%m-%d')})"

    # CPI: 2nd Tuesday each month, 13:30 UTC
    cpi_day = _second_tuesday(now.year, now.month)
    if cpi_day is not None:
        cpi_time = datetime(now.year, now.month, cpi_day, 13, 30, tzinfo=timezone.utc)
        if _within(now, cpi_time, buffer_minutes):
            return True, "CPI (est. 13:30 UTC)"

    # 2. Live Economic Calendar Feed (Checked during live trading ticks)
    if is_live_tick:
        live_events = fetch_live_calendar()
        for ev in live_events:
            date_str = ev.get("date")
            if not date_str:
                continue
            try:
                ev_time = datetime.fromisoformat(date_str)
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)
                if _within(now, ev_time, buffer_minutes):
                    return True, f"Live News: {ev.get('title')} ({ev_time.strftime('%H:%M')} UTC)"
            except Exception:
                continue

    return False, ""

