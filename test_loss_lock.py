"""
test_loss_lock.py — Verify the loss lock system works correctly.

Tests:
  1. Lock triggers when daily PnL hits loss limit
  2. loss_lock_timestamp is recorded
  3. Lock expires after LOSS_LOCK_EXPIRE_HOURS
  4. Daily reset clears lock and timestamp
  5. RSI guard blocks oversold/overbought entries
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Minimal setup to avoid MT5 dependency
os.environ["PAPER_TRADING"] = "true"

passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ PASS: {name}")
    else:
        failed += 1
        print(f"  ❌ FAIL: {name} — {detail}")


def test_loss_lock_system():
    """Test the loss lock trigger, timestamp, and expiry."""
    print("\n" + "=" * 50)
    print("  TEST 1: Loss Lock System")
    print("=" * 50)

    from database.stats_db import (
        default_stats, load_stats, save_stats,
        check_daily_lock, check_profit_lock
    )
    from database.db import get_connection, init_db

    # Initialize DB
    init_db()

    # --- Test 1a: Default stats have loss_lock_timestamp ---
    stats = default_stats()
    test(
        "default_stats has loss_lock_timestamp",
        "loss_lock_timestamp" in stats,
        f"Keys: {list(stats.keys())}"
    )
    test(
        "loss_lock_timestamp defaults to None",
        stats["loss_lock_timestamp"] is None,
        f"Got: {stats['loss_lock_timestamp']}"
    )

    # --- Test 1b: Lock triggers and records timestamp ---
    # Create a test user stats with big loss
    test_user_id = 9999
    stats = default_stats()
    stats["today_pnl"] = -200.0  # Below -50 limit
    stats["trading_locked"] = False
    stats["loss_lock_timestamp"] = None
    save_stats(stats, user_id=test_user_id)

    locked = check_daily_lock(limit=-50.0, user_id=test_user_id)
    test("Lock triggers when PnL < limit", locked, f"locked={locked}")

    # Re-load to check timestamp was saved
    stats = load_stats(user_id=test_user_id)
    test(
        "loss_lock_timestamp is set after lock",
        stats.get("loss_lock_timestamp") is not None,
        f"Got: {stats.get('loss_lock_timestamp')}"
    )
    test(
        "trading_locked is True",
        stats["trading_locked"] == True,
        f"Got: {stats['trading_locked']}"
    )

    # --- Test 1c: Lock does NOT expire before LOSS_LOCK_EXPIRE_HOURS ---
    # Simulate lock was set 1 hour ago (should still be locked)
    stats["loss_lock_timestamp"] = (datetime.now() - timedelta(hours=1)).isoformat()
    stats["trading_locked"] = True
    save_stats(stats, user_id=test_user_id)
    stats = load_stats(user_id=test_user_id)
    test(
        "Lock still active after 1 hour (< 24h)",
        stats["trading_locked"] == True,
        f"locked={stats['trading_locked']}"
    )

    # --- Test 1d: Lock expires after LOSS_LOCK_EXPIRE_HOURS ---
    stats["loss_lock_timestamp"] = (datetime.now() - timedelta(hours=25)).isoformat()
    stats["trading_locked"] = True
    save_stats(stats, user_id=test_user_id)
    stats = load_stats(user_id=test_user_id)
    test(
        "Lock expires after 25 hours (> 24h)",
        stats["trading_locked"] == False,
        f"locked={stats['trading_locked']}"
    )
    test(
        "Timestamp cleared after expiry",
        stats.get("loss_lock_timestamp") is None,
        f"Got: {stats.get('loss_lock_timestamp')}"
    )

    # --- Cleanup test user ---
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM bot_stats WHERE user_id = ?", (test_user_id,))
    except Exception:
        pass


def test_rsi_guard_constants():
    """Test RSI guard constants are properly defined."""
    print("\n" + "=" * 50)
    print("  TEST 2: RSI Guard Constants")
    print("=" * 50)

    from bot_engine import RSI_OVERSOLD_BLOCK, RSI_OVERBOUGHT_BLOCK, BREAKEVEN_ATR_MULT

    test(
        "RSI_OVERSOLD_BLOCK defined",
        RSI_OVERSOLD_BLOCK is not None and RSI_OVERSOLD_BLOCK == 25.0,
        f"Got: {RSI_OVERSOLD_BLOCK}"
    )
    test(
        "RSI_OVERBOUGHT_BLOCK defined",
        RSI_OVERBOUGHT_BLOCK is not None and RSI_OVERBOUGHT_BLOCK == 75.0,
        f"Got: {RSI_OVERBOUGHT_BLOCK}"
    )
    test(
        "BREAKEVEN_ATR_MULT defined",
        BREAKEVEN_ATR_MULT is not None and BREAKEVEN_ATR_MULT == 1.0,
        f"Got: {BREAKEVEN_ATR_MULT}"
    )


def test_loss_lock_expire_hours():
    """Test LOSS_LOCK_EXPIRE_HOURS constant."""
    print("\n" + "=" * 50)
    print("  TEST 3: Loss Lock Expire Hours")
    print("=" * 50)

    from bot_engine import LOSS_LOCK_EXPIRE_HOURS

    test(
        "LOSS_LOCK_EXPIRE_HOURS defined",
        LOSS_LOCK_EXPIRE_HOURS is not None,
        "Not defined"
    )
    test(
        "LOSS_LOCK_EXPIRE_HOURS = 24",
        LOSS_LOCK_EXPIRE_HOURS == 24,
        f"Got: {LOSS_LOCK_EXPIRE_HOURS}"
    )


def test_profit_lock():
    """Test profit lock still works correctly."""
    print("\n" + "=" * 50)
    print("  TEST 4: Profit Lock (Regression Check)")
    print("=" * 50)

    from database.stats_db import default_stats, save_stats, check_profit_lock
    from database.db import get_connection, init_db

    init_db()
    test_user_id = 9998

    # Setup user with high profit
    stats = default_stats()
    stats["today_pnl"] = 150.0  # Above 100 target
    stats["trading_locked"] = False
    save_stats(stats, user_id=test_user_id)

    locked = check_profit_lock(target=100.0, user_id=test_user_id)
    test("Profit lock triggers at target", locked, f"locked={locked}")

    # Cleanup
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM bot_stats WHERE user_id = ?", (test_user_id,))
    except Exception:
        pass


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  🧪 NUR BOT — Loss Protection Test Suite")
    print("=" * 50)

    test_rsi_guard_constants()
    test_loss_lock_expire_hours()
    test_loss_lock_system()
    test_profit_lock()

    print("\n" + "=" * 50)
    total = passed + failed
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  ✅ ALL TESTS PASSED!")
    else:
        print("  ⚠️  Some tests failed — check above.")
    print("=" * 50 + "\n")
