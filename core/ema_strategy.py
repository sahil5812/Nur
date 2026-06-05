"""
200 EMA Crossover Strategy for Nur.

Simple strategy for XAUUSD M1 with 200 EMA crossover logic.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple


class EMAStrategy:
    """
    200 EMA Crossover Strategy:
    - BUY when candle closes above EMA200 AND previous candle closed below
    - SELL when candle closes below EMA200 AND previous candle closed above
    - Uses wait_for_close=True (no repainting)
    """
    
    def __init__(self, ema_period: int = 200) -> None:
        """
        Initialize EMA strategy.
        
        Args:
            ema_period: Period for EMA calculation (default: 200)
        """
        self.ema_period: int = ema_period
        self.name: str = f"200_EMA_Crossover"
        
    def calculate_ema(self, df: pd.DataFrame, price_col: str = 'close') -> pd.Series:
        """
        Calculate EMA on a DataFrame.
        
        Args:
            df: DataFrame with price data
            price_col: Column name for price (default: 'close')
            
        Returns:
            Series with EMA values
        """
        return df[price_col].ewm(span=self.ema_period, adjust=False).mean()
    
    def get_signal(self, df: pd.DataFrame, current_idx: int) -> Optional[str]:
        """
        Get trading signal for current candle.
        
        Args:
            df: DataFrame with market data and EMA column
            current_idx: Index of current candle
            
        Returns:
            'BUY', 'SELL', or None
        """
        if current_idx < self.ema_period + 1:
            return None  # Not enough data
        
        try:
            # Get current and previous candles
            current_candle = df.iloc[current_idx]
            prev_candle = df.iloc[current_idx - 1]
            
            # Get EMA values
            ema_current = df['ema_200'].iloc[current_idx]
            ema_previous = df['ema_200'].iloc[current_idx - 1]
            
            # Current close relative to EMA
            current_close: float = current_candle['close']
            prev_close: float = prev_candle['close']
            
            # BUY Signal: Crossover ABOVE EMA
            if (prev_close <= ema_previous and  # Previous was below or on EMA
                current_close > ema_current):   # Current closed above EMA
                return 'BUY'
            
            # SELL Signal: Crossover BELOW EMA
            elif (prev_close >= ema_previous and  # Previous was above or on EMA
                  current_close < ema_current):   # Current closed below EMA
                return 'SELL'
            
            return None
            
        except Exception as e:
            print(f"Error in EMA strategy: {e}")
            return None
    
    def should_exit_early(
        self,
        df: pd.DataFrame,
        current_idx: int,
        trade_direction: str,
        entry_price: float,
        current_price: float,
        candles_in_trade: int,
        max_candles: int = 50
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if we should exit trade early.
        
        Early exit conditions:
        1. Cross back over EMA (opposite signal)
        2. Price stagnation (small movement for many candles)
        3. Too many candles without progress
        
        Args:
            df: DataFrame with market data
            current_idx: Current candle index
            trade_direction: 'BUY' or 'SELL'
            entry_price: Entry price of the trade
            current_price: Current market price
            candles_in_trade: Number of candles since entry
            max_candles: Maximum candles before forced exit
            
        Returns:
            Tuple of (should_exit: bool, reason: str or None)
        """
        if candles_in_trade <= 5:  # Give trade time to develop
            return False, None
        
        current_candle = df.iloc[current_idx]
        prev_candle = df.iloc[current_idx - 1]
        
        current_close: float = current_candle['close']
        ema_current = df['ema_200'].iloc[current_idx]
        ema_previous = df['ema_200'].iloc[current_idx - 1]
        
        # 1. Cross back over EMA (opposite signal)
        if trade_direction == 'BUY':
            if prev_candle['close'] > ema_previous and current_close < ema_current:
                return True, "Early: Crossed back below EMA"
        elif trade_direction == 'SELL':
            if prev_candle['close'] < ema_previous and current_close > ema_current:
                return True, "Early: Crossed back above EMA"
        
        # 2. Too many candles without significant progress
        if candles_in_trade > max_candles:
            return True, f"Early: {max_candles} candles without target"
        
        # 3. Check if price moved against us significantly after initial move
        if candles_in_trade > 10:
            if trade_direction == 'BUY':
                # If price went up but now back near entry
                highest = df['high'].iloc[current_idx-candles_in_trade:current_idx+1].max()
                if highest > entry_price * 1.002:  # Went up 0.2%
                    if current_price < entry_price * 0.999:  # Now down 0.1%
                        return True, "Early: Gave back gains"
            
            elif trade_direction == 'SELL':
                # If price went down but now back near entry
                lowest = df['low'].iloc[current_idx-candles_in_trade:current_idx+1].min()
                if lowest < entry_price * 0.998:  # Went down 0.2%
                    if current_price > entry_price * 1.001:  # Now up 0.1%
                        return True, "Early: Gave back gains"
        
        return False, None


# Test function
def test_ema_strategy() -> EMAStrategy:
    """Test the EMA strategy"""
    print("Testing EMA Strategy...")
    
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=500, freq='1min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.randn(500).cumsum() + 2000,
        'high': np.random.randn(500).cumsum() + 2005,
        'low': np.random.randn(500).cumsum() + 1995,
        'close': np.random.randn(500).cumsum() + 2000,
        'volume': np.random.randint(100, 1000, 500)
    })
    
    # Calculate EMA
    strategy = EMAStrategy(ema_period=200)
    df['ema_200'] = strategy.calculate_ema(df)
    
    # Test signals
    signals = []
    for i in range(201, 300):
        signal = strategy.get_signal(df, i)
        if signal:
            signals.append((i, signal))
    
    print(f"Found {len(signals)} signals")
    for idx, sig in signals[:5]:
        print(f"  Candle {idx}: {sig}")
    
    return strategy

if __name__ == "__main__":
    test_ema_strategy()
