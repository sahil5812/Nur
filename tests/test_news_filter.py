from datetime import datetime, timezone, timedelta
from intelligence.news_filter import is_news_window


def test_nfp_blackout_window() -> None:
    """NFP on first Friday at 13:30 UTC should block trading."""
    now = datetime(2026, 6, 5, 13, 30, tzinfo=timezone.utc)
    assert is_news_window(now=now, buffer_minutes=30) == (True, "NFP (13:30 UTC)")


def test_fomc_blackout_window() -> None:
    """FOMC on 2026-06-17 at 18:00 UTC should block trading."""
    now = datetime(2026, 6, 17, 18, 0, tzinfo=timezone.utc)
    assert is_news_window(now=now, buffer_minutes=30) == (True, "FOMC (2026-06-17)")


def test_cpi_blackout_window() -> None:
    """CPI on second Tuesday at 13:30 UTC should block trading."""
    now = datetime(2026, 6, 9, 13, 30, tzinfo=timezone.utc)
    assert is_news_window(now=now, buffer_minutes=30) == (True, "CPI (est. 13:30 UTC)")


def test_news_buffer_minutes_configurable() -> None:
    """Custom buffer should be respected."""
    outside_default = datetime(2026, 6, 5, 12, 59, tzinfo=timezone.utc)
    inside_custom = datetime(2026, 6, 5, 12, 59, tzinfo=timezone.utc)

    assert is_news_window(now=outside_default, buffer_minutes=30) == (False, "")
    assert is_news_window(now=inside_custom, buffer_minutes=31) == (True, "NFP (13:30 UTC)")


def test_no_news_window() -> None:
    """Non-news dates should not block trading."""
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    assert is_news_window(now=now, buffer_minutes=30) == (False, "")