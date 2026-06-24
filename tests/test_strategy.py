import pytest
import MetaTrader5 as mt5
from core.strategy import PullbackStrategy
from core.models import Bar, StrategyConfig


def create_synthetic_bars(count: int, base_price: float, trend_slope: float = 0.0) -> list[Bar]:
    """Helper to generate a list of Bar objects with specified price movement."""
    bars = []
    for i in range(count):
        price = base_price + (i * trend_slope)
        bars.append(
            Bar(
                time=1000 + i * 60,
                open=price,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                tick_volume=10
            )
        )
    return bars


@pytest.fixture
def strategy_config():
    return StrategyConfig(
        symbol="XAUUSD",
        ema_period=10,  # small EMA period for quick testing
        atr_period=5,
        atr_multiplier=0.5,
        cooldown_seconds=10,
        ema_min_buffer=0.15,
    )


@pytest.fixture
def strategy(strategy_config):
    return PullbackStrategy(strategy_config)


class TestPullbackStrategy:
    def test_insufficient_bars_guard(self, strategy):
        # Config requires ema_period (10) + 3 = 13 bars
        m1_bars = create_synthetic_bars(12, 1800.0)
        m5_bars = create_synthetic_bars(15, 1800.0)
        h1_bars = create_synthetic_bars(15, 1800.0)

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=False)
        assert sig is None
        assert "Insufficient bars data" in log

    def test_bullish_setup_pullback_and_buy_trigger(self, strategy):
        # We need at least 13 bars for all timeframes
        # 1. Setup H1 and M5 as strongly bullish: close is far above EMA
        h1_bars = create_synthetic_bars(20, 1800.0, trend_slope=1.0)
        m5_bars = create_synthetic_bars(20, 1800.0, trend_slope=1.0)

        # 2. Test Pullback detection on M1
        # EMA of 10 values of 1800.0 is 1800.0
        # Let's make current_m1_close close to EMA (1800.0) -> e.g. 1800.05
        m1_bars = create_synthetic_bars(20, 1800.0)
        # Modify the last close to trigger pullback (diff < 0.15)
        m1_bars[-1].close = 1800.05
        m1_bars[-1].high = 1800.1
        m1_bars[-1].low = 1800.0

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=False)
        assert sig is None
        assert pullback is True  # Pullback should be spotted

        # 3. Test Buy trigger (breakout from EMA)
        # Pullback is already seen (pullback_seen=True)
        # Now current close is above EMA: e.g. 1800.5
        # And prev close (bars[-3]) < last close (bars[-2]) to indicate upward trend
        m1_bars = create_synthetic_bars(20, 1800.0)
        m1_bars[-3].close = 1799.8  # prev_m1_close
        m1_bars[-2].close = 1800.0  # last_m1_close
        m1_bars[-1].close = 1800.5  # current_m1_close (above EMA)
        
        # Make ATR small enough so we pass the consolidation filter (diff > atr * multiplier)
        # With atr around 0.1, atr * multiplier is 0.05, and diff is 0.5 > 0.05
        for b in m1_bars:
            b.high = b.close + 0.05
            b.low = b.close - 0.05

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=True)
        assert sig == mt5.ORDER_TYPE_BUY
        assert pullback is False  # Pullback flag should reset

    def test_bearish_setup_pullback_and_sell_trigger(self, strategy):
        # 1. Setup H1 and M5 as strongly bearish: close is far below EMA
        # Base price 1700, EMA around 1750
        h1_bars = create_synthetic_bars(20, 1700.0, trend_slope=-1.0)
        m5_bars = create_synthetic_bars(20, 1700.0, trend_slope=-1.0)

        # 2. Test Pullback detection on M1 (near 1700.0 EMA)
        m1_bars = create_synthetic_bars(20, 1700.0)
        m1_bars[-1].close = 1699.95

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=False)
        assert sig is None
        assert pullback is True

        # 3. Test Sell trigger (breakdown from EMA)
        # Now current close is below EMA: e.g. 1699.5
        # And prev close (1700.2) > last close (1700.0)
        m1_bars = create_synthetic_bars(20, 1700.0)
        m1_bars[-3].close = 1700.2
        m1_bars[-2].close = 1700.0
        m1_bars[-1].close = 1699.4
        
        for b in m1_bars:
            b.high = b.close + 0.05
            b.low = b.close - 0.05

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=True)
        assert sig == mt5.ORDER_TYPE_SELL
        assert pullback is False

    def test_trends_misaligned_resets_pullback(self, strategy):
        # H1 is Bullish (1850 vs 1800), M5 is Bearish (1750 vs 1800)
        h1_bars = create_synthetic_bars(20, 1850.0)
        m5_bars = create_synthetic_bars(20, 1750.0)
        m1_bars = create_synthetic_bars(20, 1800.0)

        sig, pullback, log = strategy.check_signals(m1_bars, m5_bars, h1_bars, pullback_seen=True)
        assert sig is None
        assert pullback is False  # pullback should be reset to False
