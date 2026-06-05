"""
intelligence/news_filter.py — High-impact news blackout window checker.

Blocks trading 30 min before and after: NFP, FOMC, CPI.
XAUUSD moves 200–500 pips on these events — never trade through them.
"""
from datetime import datetime, timezone, timedelta
from utils.logger import get_logger

logger = get_logger(__name__)

BUFFER_MINUTES = 30

# FOMC dates 2025-2026 (year, month, day) — decision at ~18:00 UTC
_FOMC = {
    (2025,1,29),(2025,3,19),(2025,5,7),(2025,6,18),
    (2025,7,30),(2025,9,17),(2025,10,29),(2025,12,10),
    (2026,1,28),(2026,3,18),(2026,4,29),(2026,6,17),
    (2026,7,29),(2026,9,16),(2026,10,28),(2026,12,9),
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


def _within(now: datetime, event: datetime) -> bool:
    return abs((now - event).total_seconds()) / 60 <= BUFFER_MINUTES


def is_news_window(now: datetime | None = None) -> tuple[bool, str]:
    """
    Returns (True, event_name) if inside a news blackout, else (False, "").
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # NFP: 1st Friday each month, 13:30 UTC
    nfp_day  = _first_friday(now.year, now.month)
    nfp_time = datetime(now.year, now.month, nfp_day, 13, 30, tzinfo=timezone.utc)
    if _within(now, nfp_time):
        return True, f"NFP ({nfp_time.strftime('%H:%M')} UTC)"

    # FOMC: hardcoded dates, 18:00 UTC
    for (y, mo, d) in _FOMC:
        t = datetime(y, mo, d, 18, 0, tzinfo=timezone.utc)
        if _within(now, t):
            return True, f"FOMC ({t.strftime('%Y-%m-%d')})"

    # CPI: ~2nd Tuesday each month, 13:30 UTC
    cpi_day = _second_tuesday(now.year, now.month)
    if cpi_day:
        cpi_time = datetime(now.year, now.month, cpi_day, 13, 30, tzinfo=timezone.utc)
        if _within(now, cpi_time):
            return True, f"CPI (est. {cpi_time.strftime('%H:%M')} UTC)"

    return False, ""
