#!/usr/bin/env python3
"""
Observer - Monitors open trades and decides when to exit early.

This module provides the TradeObserver class which monitors open trades
and decides when to exit early based on candle behavior, giving Nur agency
beyond just waiting for SL/TP.
"""

from typing import Optional, Dict, Any, List


class TradeObserver:
    """
    Monitors open trades and decides early exits based on candle behavior.
    
    Exit Triggers:
    1. Candle closes back across EMA200
    2. Strong opposite momentum candle
    3. Price stalls for N candles
    4. Time-based exit (optional)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize trade observer.
        
        Args:
            config: Configuration dictionary with observer parameters
        """
        self.config: Dict[str, Any] = config or {
            'momentum_threshold': 0.001,  # 0.1% for strong opposite candle
            'stall_candles': 10,          # Exit if price doesn't move for 10 candles
            'max_trade_duration': 60,     # Max 60 minutes per trade
            'trailing_stop_activation': 0.005,  # 0.5% profit to activate trailing
            'trailing_stop_distance': 0.002,    # 0.2% trailing distance
        }
        
        # Track trade statistics
        self.trade_stats: Dict[str, Any] = {
            'entry_price': None,
            'entry_time': None,
            'highest_price': None,
            'lowest_price': None,
            'candles_in_trade': 0,
            'direction': None,  # 'BUY' or 'SELL'
        }
        
        # Price movement tracking
        self.price_history: List[float] = []
        self.ema_history: List[float] = []
        
    def start_trade(self, direction: str, entry_price: float, entry_time: Any) -> None:
        """
        Initialize tracking for a new trade.
        
        Args:
            direction: 'BUY' or 'SELL'
            entry_price: Entry price of the trade
            entry_time: Entry timestamp
        """
        self.trade_stats = {
            'entry_price': entry_price,
            'entry_time': entry_time,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'candles_in_trade': 0,
            'direction': direction,
            'max_profit_pct': 0,
            'max_loss_pct': 0,
        }
        self.price_history = [entry_price]
        self.ema_history = []
        
        print(f"🔍 Observer started tracking {direction} trade at {entry_price:.2f}")
    
    def update(
        self,
        current_candle: Dict[str, Any],
        current_ema: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update observer with new candle data.
        
        Args:
            current_candle: dict with 'close', 'high', 'low', 'open'
            current_ema: Current EMA value (optional)
            
        Returns:
            dict with exit recommendation or None if no exit
        """
        if self.trade_stats['entry_price'] is None:
            return None
        
        self.trade_stats['candles_in_trade'] += 1
        current_price: float = current_candle['close']
        
        # Update price extremes
        if self.trade_stats['direction'] == 'BUY':
            self.trade_stats['highest_price'] = max(
                self.trade_stats['highest_price'], 
                current_candle['high']
            )
            self.trade_stats['lowest_price'] = min(
                self.trade_stats['lowest_price'], 
                current_candle['low']
            )
        else:  # SELL
            self.trade_stats['highest_price'] = max(
                self.trade_stats['highest_price'], 
                current_candle['high']
            )
            self.trade_stats['lowest_price'] = min(
                self.trade_stats['lowest_price'], 
                current_candle['low']
            )
        
        # Calculate current profit/loss percentage
        if self.trade_stats['direction'] == 'BUY':
            current_pnl_pct: float = (current_price - self.trade_stats['entry_price']) / self.trade_stats['entry_price'] * 100
        else:  # SELL
            current_pnl_pct = (self.trade_stats['entry_price'] - current_price) / self.trade_stats['entry_price'] * 100
        
        # Update max profit/loss
        self.trade_stats['max_profit_pct'] = max(
            self.trade_stats['max_profit_pct'], 
            current_pnl_pct
        )
        self.trade_stats['max_loss_pct'] = min(
            self.trade_stats['max_loss_pct'], 
            current_pnl_pct
        )
        
        # Check exit conditions
        exit_reason = self._check_exit_conditions(current_candle, current_ema, current_pnl_pct)
        
        if exit_reason:
            print(f"🔍 Observer recommends exit: {exit_reason}")
            print(f"   Trade duration: {self.trade_stats['candles_in_trade']} candles")
            print(f"   Max profit: {self.trade_stats['max_profit_pct']:.2f}%, "
                  f"Current: {current_pnl_pct:.2f}%")
            
            return {
                'exit_price': current_price,
                'exit_reason': exit_reason,
                'pnl_pct': current_pnl_pct,
                'candles_in_trade': self.trade_stats['candles_in_trade'],
                'max_profit_pct': self.trade_stats['max_profit_pct'],
                'max_loss_pct': self.trade_stats['max_loss_pct'],
            }
        
        # Store price and EMA for stall detection
        self.price_history.append(current_price)
        if current_ema is not None:
            self.ema_history.append(current_ema)
        
        # Keep only last N prices for stall detection
        if len(self.price_history) > self.config['stall_candles']:
            self.price_history.pop(0)
            if self.ema_history:
                self.ema_history.pop(0)
        
        return None
    
    def _check_exit_conditions(
        self,
        candle: Dict[str, Any],
        ema: Optional[float],
        current_pnl_pct: float
    ) -> Optional[str]:
        """
        Check all exit conditions.
        
        Args:
            candle: Current candle data
            ema: Current EMA value
            current_pnl_pct: Current profit/loss percentage
            
        Returns:
            Exit reason string or None
        """
        # 1. Candle closes back across EMA200
        if self._check_ema_crossback(candle, ema):
            return "EMA crossback"
        
        # 2. Strong opposite momentum candle
        if self._check_strong_opposite_candle(candle):
            return "Strong opposite momentum"
        
        # 3. Price stalls for N candles
        if self._check_price_stall():
            return f"Price stalled for {self.config['stall_candles']} candles"
        
        # 4. Time-based exit
        if self._check_time_exit():
            return f"Max duration reached ({self.config['max_trade_duration']} candles)"
        
        # 5. Trailing stop (if profit threshold reached)
        trailing_exit = self._check_trailing_stop(candle, current_pnl_pct)
        if trailing_exit:
            return trailing_exit
        
        return None
    
    def _check_ema_crossback(
        self,
        candle: Dict[str, Any],
        ema: Optional[float]
    ) -> bool:
        """
        Check if price closes back across EMA.
        
        Args:
            candle: Current candle data
            ema: Current EMA value
            
        Returns:
            True if crossback detected
        """
        if ema is None:
            return False
        
        current_close: float = candle['close']
        direction: str = self.trade_stats['direction']
        
        if direction == 'BUY':
            # For BUY trade, exit if closes below EMA
            return current_close < ema
        else:  # SELL
            # For SELL trade, exit if closes above EMA
            return current_close > ema
    
    def _check_strong_opposite_candle(self, candle: Dict[str, Any]) -> bool:
        """
        Check for strong opposite momentum candle.
        
        Args:
            candle: Current candle data
            
        Returns:
            True if strong opposite candle detected
        """
        direction: str = self.trade_stats['direction']
        body_size: float = abs(candle['close'] - candle['open'])
        candle_range: float = candle['high'] - candle['low']
        
        # Avoid division by zero
        if candle_range == 0:
            return False
        
        # Calculate body-to-range ratio
        body_ratio: float = body_size / candle_range
        
        # Strong candle has large body relative to range
        if body_ratio < 0.7:  # Not a strong candle
            return False
        
        # Check if it's opposite to our direction
        if direction == 'BUY':
            # Strong bearish candle (close < open)
            is_bearish: bool = candle['close'] < candle['open']
            return is_bearish and body_size > (self.trade_stats['entry_price'] * self.config['momentum_threshold'])
        else:  # SELL
            # Strong bullish candle (close > open)
            is_bullish: bool = candle['close'] > candle['open']
            return is_bullish and body_size > (self.trade_stats['entry_price'] * self.config['momentum_threshold'])
    
    def _check_price_stall(self) -> bool:
        """
        Check if price has stalled (not moved much for N candles).
        
        Returns:
            True if price has stalled
        """
        if len(self.price_history) < self.config['stall_candles']:
            return False
        
        # Calculate price range over last N candles
        price_range: float = max(self.price_history) - min(self.price_history)
        avg_price: float = sum(self.price_history) / len(self.price_history)
        
        # If range is less than 0.1% of average price, consider it stalled
        if avg_price == 0:
            return False
        
        stall_threshold: float = avg_price * 0.001  # 0.1%
        return price_range < stall_threshold
    
    def _check_time_exit(self) -> bool:
        """
        Exit if trade has been open too long.
        
        Returns:
            True if max duration reached
        """
        return self.trade_stats['candles_in_trade'] >= self.config['max_trade_duration']
    
    def _check_trailing_stop(
        self,
        candle: Dict[str, Any],
        current_pnl_pct: float
    ) -> Optional[str]:
        """
        Check trailing stop conditions.
        
        Args:
            candle: Current candle data
            current_pnl_pct: Current profit/loss percentage
            
        Returns:
            Exit reason string or None
        """
        direction: str = self.trade_stats['direction']
        current_price: float = candle['close']
        
        # Only activate trailing stop after certain profit
        if abs(current_pnl_pct) < self.config['trailing_stop_activation'] * 100:
            return None
        
        # Calculate trailing stop level
        if direction == 'BUY':
            # For BUY, trailing stop is below highest price
            trail_stop_price: float = self.trade_stats['highest_price'] * (1 - self.config['trailing_stop_distance'])
            if current_price <= trail_stop_price:
                return f"Trailing stop hit ({current_pnl_pct:.2f}% profit)"
        else:  # SELL
            # For SELL, trailing stop is above lowest price
            trail_stop_price = self.trade_stats['lowest_price'] * (1 + self.config['trailing_stop_distance'])
            if current_price >= trail_stop_price:
                return f"Trailing stop hit ({current_pnl_pct:.2f}% profit)"
        
        return None
    
    def get_trade_stats(self) -> Dict[str, Any]:
        """
        Get current trade statistics.
        
        Returns:
            Copy of trade statistics dictionary
        """
        return self.trade_stats.copy()


# Test function - FIXED VERSION
def test_observer() -> None:
    """Test observer functionality"""
    print("🧪 Testing Trade Observer")
    print("=" * 50)
    
    observer = TradeObserver()
    
    # Simulate a BUY trade
    print("\n1. Starting BUY trade at 2050.00")
    observer.start_trade('BUY', 2050.00, '2024-01-01 10:00:00')
    
    # Test 1: Normal candle (no exit)
    print("\n2. Normal candle (should not exit):")
    candle1 = {'open': 2050.50, 'high': 2051.00, 'low': 2050.00, 'close': 2050.80}
    result1 = observer.update(candle1, 2049.50)  # FIXED: positional argument
    print(f"   Result: {result1}")
    
    # Test 2: Strong opposite candle
    print("\n3. Strong opposite candle (should exit):")
    candle2 = {'open': 2051.00, 'high': 2051.50, 'low': 2048.00, 'close': 2048.50}
    result2 = observer.update(candle2, 2049.80)  # FIXED: positional argument
    print(f"   Result: {result2}")
    
    # Start new trade for EMA crossback test
    print("\n4. Starting new BUY trade at 2050.00")
    observer2 = TradeObserver()
    observer2.start_trade('BUY', 2050.00, '2024-01-01 10:00:00')
    
    # Test 3: EMA crossback
    print("\n5. Candle closes below EMA (should exit):")
    candle3 = {'open': 2049.50, 'high': 2050.00, 'low': 2048.50, 'close': 2048.80}
    result3 = observer2.update(candle3, 2049.50)  # FIXED: positional argument
    print(f"   Result: {result3}")
    
    # Test stall detection
    print("\n6. Testing stall detection (simulate 10 similar candles):")
    observer3 = TradeObserver({'stall_candles': 3})  # Shorter for test
    observer3.start_trade('BUY', 2050.00, '2024-01-01 10:00:00')
    
    for i in range(5):
        candle = {'open': 2050.00 + i*0.01, 'high': 2050.10 + i*0.01, 
                  'low': 2049.95 + i*0.01, 'close': 2050.05 + i*0.01}
        result = observer3.update(candle, 2049.50)  # FIXED: positional argument
        if result:
            print(f"   Candle {i+1}: Exit - {result['exit_reason']}")
            break
        else:
            print(f"   Candle {i+1}: No exit")


if __name__ == "__main__":
    test_observer()
