import MetaTrader5 as mt5
from typing import List, Tuple, Optional
from core.models import Bar, Tick, StrategyConfig
from utils.logger import logger
from utils.helpers import safe_divide

class PullbackStrategy:
    TREND_NONE = "NONE"
    TREND_BULLISH = "BULLISH"
    TREND_BEARISH = "BEARISH"

    def __init__(self, config: StrategyConfig):
        self.config = config

    def calculate_ema(self, values: List[float], period: int) -> float:
        """
        Calculates the Exponential Moving Average (EMA).
        Matches original formula exactly.
        """
        if not values:
            return 0.0
        k = 2.0 / (period + 1.0)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1.0 - k)
        return ema

    def calculate_atr(self, bars: List[Bar], period: int) -> float:
        """
        Calculates Average True Range (ATR) over the last N bars.
        Matches original formula exactly.
        """
        if len(bars) < period + 1:
            return 0.0
            
        atr_values = []
        # Calculate true range for the last 'period' bars
        for i in range(-period, 0):
            current_bar = bars[i]
            prev_bar = bars[i - 1]
            tr = max(
                current_bar.high - current_bar.low,
                abs(current_bar.high - prev_bar.close),
                abs(current_bar.low - prev_bar.close)
            )
            atr_values.append(tr)
            
        return sum(atr_values) / period

    def check_signals(self, 
                      m1_bars: List[Bar], 
                      m5_bars: List[Bar], 
                      h1_bars: List[Bar], 
                      pullback_seen: bool) -> Tuple[Optional[int], bool, str]:
        """
        Executes MTF Logic:
        - H1 Direction: Close price vs H1 EMA200
        - M5 Structure: Close price vs M5 EMA200 (Confirmation)
        - M1 Execution: Close price vs M1 EMA200 (Pullback & entry trigger)
        
        Returns: (signal_type, updated_pullback_seen, log_message)
        """
        # Ensure we have enough data
        req_len = self.config.ema_period + 3
        if len(m1_bars) < req_len or len(m5_bars) < req_len or len(h1_bars) < req_len:
            return None, pullback_seen, "Insufficient bars data for EMA/ATR calculation."

        # M1 Data
        m1_closes = [b.close for b in m1_bars]
        m1_ema = self.calculate_ema(m1_closes[-self.config.ema_period:], self.config.ema_period)
        m1_atr = self.calculate_atr(m1_bars, self.config.atr_period)
        
        last_m1_close = m1_bars[-2].close
        prev_m1_close = m1_bars[-3].close
        current_m1_close = m1_bars[-1].close # Active bar close

        # H1 Trend Direction
        h1_closes = [b.close for b in h1_bars]
        h1_ema = self.calculate_ema(h1_closes[-self.config.ema_period:], self.config.ema_period)
        last_h1_close = h1_bars[-2].close
        
        if last_h1_close > h1_ema:
            h1_trend = self.TREND_BULLISH
        elif last_h1_close < h1_ema:
            h1_trend = self.TREND_BEARISH
        else:
            h1_trend = self.TREND_NONE

        # M5 Structure Confirmation
        m5_closes = [b.close for b in m5_bars]
        m5_ema = self.calculate_ema(m5_closes[-self.config.ema_period:], self.config.ema_period)
        last_m5_close = m5_bars[-2].close
        
        if last_m5_close > m5_ema:
            m5_trend = self.TREND_BULLISH
        elif last_m5_close < m5_ema:
            m5_trend = self.TREND_BEARISH
        else:
            m5_trend = self.TREND_NONE

        # Log status snippet
        log_msg = (
            f"M1={current_m1_close:.2f} (EMA={m1_ema:.2f}) | "
            f"M5={m5_trend} ({last_m5_close:.2f}/EMA={m5_ema:.2f}) | "
            f"H1={h1_trend} ({last_h1_close:.2f}/EMA={h1_ema:.2f})"
        )

        # Signal logic matching original flow with M5 structure check added
        # BULLISH SETUP
        if h1_trend == self.TREND_BULLISH and m5_trend == self.TREND_BULLISH:
            # 1. Check for pullback
            if abs(current_m1_close - m1_ema) < self.config.ema_min_buffer:
                pullback_seen = True
                logger.info("📈 Pullback spotted on M1 (Bullish Setup)")
                
            # 2. Trigger order on bullish breakout
            elif pullback_seen and current_m1_close > m1_ema and prev_m1_close < last_m1_close:
                if abs(current_m1_close - m1_ema) < (m1_atr * self.config.atr_multiplier):
                    return None, pullback_seen, f"{log_msg} | Filtered: Price in consolidation (too close to M1 EMA)"
                return mt5.ORDER_TYPE_BUY, False, f"{log_msg} | 🟢 BUY TRIGGERED"

        # BEARISH SETUP
        elif h1_trend == self.TREND_BEARISH and m5_trend == self.TREND_BEARISH:
            # 1. Check for pullback
            if abs(current_m1_close - m1_ema) < self.config.ema_min_buffer:
                pullback_seen = True
                logger.info("📉 Pullback spotted on M1 (Bearish Setup)")
                
            # 2. Trigger order on bearish breakdown
            elif pullback_seen and current_m1_close < m1_ema and prev_m1_close > last_m1_close:
                if abs(current_m1_close - m1_ema) < (m1_atr * self.config.atr_multiplier):
                    return None, pullback_seen, f"{log_msg} | Filtered: Price in consolidation (too close to M1 EMA)"
                return mt5.ORDER_TYPE_SELL, False, f"{log_msg} | 🔴 SELL TRIGGERED"
                
        else:
            # If trends disagree, we reset pullback state
            if pullback_seen:
                logger.info("🔄 Trends misaligned, resetting pullback tracker.")
                pullback_seen = False

        return None, pullback_seen, log_msg
