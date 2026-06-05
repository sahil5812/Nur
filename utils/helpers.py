from datetime import datetime, time, timezone, timedelta
from typing import Union

def parse_time_offset(offset_str: str) -> timezone:
    """
    Parses offset string like '+02:00' or '-05:00' or 'UTC+3' into a timezone object.
    """
    try:
        offset_str = offset_str.upper().replace("UTC", "").strip()
        if not offset_str or offset_str == "Z":
            return timezone.utc
        
        sign = 1
        if offset_str.startswith("-"):
            sign = -1
            offset_str = offset_str[1:]
        elif offset_str.startswith("+"):
            offset_str = offset_str[1:]
            
        parts = offset_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        
        return timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
    except Exception:
        return timezone.utc

def is_time_in_range(current_dt: datetime, start_time: time, end_time: time, tz: timezone) -> bool:
    """
    Checks if current datetime adjusted for the given timezone is within start_time and end_time.
    Handles overnight ranges (e.g., 22:00 to 04:00).
    """
    tz_now = current_dt.astimezone(tz)
    check_time = tz_now.time()
    
    if start_time <= end_time:
        return start_time <= check_time <= end_time
    else: # Overnight
        return check_time >= start_time or check_time <= end_time

def format_duration(seconds: float) -> str:
    """
    Formats a duration in seconds to a human-readable string (e.g. 4m 12s, 1h 5m).
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Performs division safely, returning default if division by zero occurs.
    """
    try:
        if denominator == 0.0:
            return default
        return numerator / denominator
    except ZeroDivisionError:
        return default
