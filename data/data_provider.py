import time
import MetaTrader5 as mt5
from typing import List, Optional, Dict, Tuple
from core.models import Bar, Tick
from utils.logger import logger

class DataProvider:
    def __init__(self, cache_ttl_seconds: float = 1.0):
        self.cache_ttl = cache_ttl_seconds
        # Key: (symbol, timeframe, count) -> Value: (timestamp, list of Bars)
        self._rates_cache: Dict[Tuple[str, int, int], Tuple[float, List[Bar]]] = {}
        # Key: symbol -> Value: (timestamp, Tick)
        self._tick_cache: Dict[str, Tuple[float, Tick]] = {}

    def get_rates(self, symbol: str, timeframe: int, count: int, force_refresh: bool = False) -> List[Bar]:
        """
        Fetches OHLC bars for a symbol and timeframe, using cached data if within TTL.
        Handles None values and exceptions safely.
        """
        now = time.time()
        cache_key = (symbol, timeframe, count)
        
        if not force_refresh and cache_key in self._rates_cache:
            cache_time, cached_bars = self._rates_cache[cache_key]
            if now - cache_time < self.cache_ttl:
                return cached_bars

        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                logger.warning(f"⚠️ copy_rates_from_pos returned None or empty for {symbol} on TF {timeframe}")
                # Return cached value even if expired as fallback, otherwise empty list
                if cache_key in self._rates_cache:
                    return self._rates_cache[cache_key][1]
                return []
            
            bars = []
            for r in rates:
                # MT5 returns rates as a numpy structured array
                bars.append(Bar(
                    time=int(r['time']),
                    open=float(r['open']),
                    high=float(r['high']),
                    low=float(r['low']),
                    close=float(r['close']),
                    tick_volume=int(r['tick_volume'])
                ))
            
            self._rates_cache[cache_key] = (now, bars)
            return bars
            
        except Exception as e:
            logger.error(f"❌ Exception in DataProvider.get_rates for {symbol}: {e}")
            if cache_key in self._rates_cache:
                return self._rates_cache[cache_key][1]
            return []

    def get_tick(self, symbol: str, force_refresh: bool = False) -> Optional[Tick]:
        """
        Fetches the current tick for a symbol, using cached data if within TTL.
        Handles None values and exceptions safely.
        """
        now = time.time()
        
        if not force_refresh and symbol in self._tick_cache:
            cache_time, cached_tick = self._tick_cache[symbol]
            if now - cache_time < self.cache_ttl:
                return cached_tick

        try:
            tick_data = mt5.symbol_info_tick(symbol)
            if tick_data is None:
                logger.warning(f"⚠️ symbol_info_tick returned None for {symbol}")
                if symbol in self._tick_cache:
                    return self._tick_cache[symbol][1]
                return None
            
            tick = Tick(
                time=int(tick_data.time),
                bid=float(tick_data.bid),
                ask=float(tick_data.ask),
                last=float(tick_data.last),
                volume=float(tick_data.volume)
            )
            
            self._tick_cache[symbol] = (now, tick)
            return tick
            
        except Exception as e:
            logger.error(f"❌ Exception in DataProvider.get_tick for {symbol}: {e}")
            if symbol in self._tick_cache:
                return self._tick_cache[symbol][1]
            return None

    def clear_cache(self):
        """Clears all cached rates and ticks."""
        self._rates_cache.clear()
        self._tick_cache.clear()
