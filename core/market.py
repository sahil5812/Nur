"""
MT5 Market Data Module - Reads and processes MT5-exported historical data.

This module handles loading MT5 CSV files and calculating EMA exactly as MT5 does.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
from typing import Optional, Dict, Any, List


class MT5MarketData:
    """
    Reads and processes MT5-exported historical data.
    Calculates EMA exactly as MT5 does.
    """
    
    def __init__(self, data_path: str) -> None:
        """
        Initialize market data loader.
        
        Args:
            data_path: Path to MT5 exported CSV file
        """
        self.data_path: str = data_path
        self.df: Optional[pd.DataFrame] = None
        self.ema_period: int = 200
        
    def load_data(self) -> bool:
        """
        Load MT5 exported CSV and convert to proper DataFrame.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # MT5 exports with semicolon delimiters and quotes
            self.df = pd.read_csv(
                self.data_path, 
                delimiter=';',
                names=['timestamp', 'open', 'high', 'low', 'close', 'tick_vol', 'real_vol', 'spread'],
                skiprows=1  # Skip header row
            )
            
            # Parse the timestamp (format: "2024.01.01 00:00")
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'].str.strip('"'), format='%Y.%m.%d %H:%M')
            
            # Convert price columns to float
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
            
            # Set timestamp as index
            self.df.set_index('timestamp', inplace=True)
            
            # Sort by time (just in case)
            self.df.sort_index(inplace=True)
            
            print(f"✅ Loaded {len(self.df)} candles from {self.data_path}")
            print(f"Date range: {self.df.index[0]} to {self.df.index[-1]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def calculate_ema_mt5(self) -> bool:
        """
        Calculate EMA in the exact same way MT5 does.
        
        MT5 uses this formula for exponential moving average:
        EMA = (Close * alpha) + (Previous EMA * (1 - alpha))
        where alpha = 2 / (period + 1)
        
        For the first EMA value, MT5 uses SMA (Simple Moving Average)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.df is None or len(self.df) < self.ema_period:
            print(f"❌ Not enough data for {self.ema_period}-period EMA")
            return False
        
        alpha: float = 2 / (self.ema_period + 1)
        
        # Calculate SMA for the first EMA value
        sma_initial = self.df['close'].rolling(window=self.ema_period).mean()
        
        # Calculate EMA using the recursive formula
        ema_values: List[float] = []
        
        for i in range(len(self.df)):
            if i < self.ema_period - 1:
                # Not enough data yet
                ema_values.append(np.nan)
            elif i == self.ema_period - 1:
                # First EMA value = SMA
                ema_values.append(sma_initial.iloc[i])
            else:
                # EMA = (Close * alpha) + (Previous EMA * (1 - alpha))
                current_close: float = self.df['close'].iloc[i]
                prev_ema: float = ema_values[-1]
                current_ema: float = (current_close * alpha) + (prev_ema * (1 - alpha))
                ema_values.append(current_ema)
        
        self.df['ema_200'] = ema_values
        
        print(f"✅ Calculated EMA{self.ema_period} for {len(self.df)} candles")
        print(f"First EMA value: {self.df['ema_200'].iloc[self.ema_period]}")
        
        return True
    
    def get_candle(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get candle data at specific index.
        
        Args:
            index: Candle index
            
        Returns:
            Dictionary with candle data or None if index out of range
        """
        if self.df is None or index >= len(self.df):
            return None
        
        return {
            'timestamp': self.df.index[index],
            'open': self.df['open'].iloc[index],
            'high': self.df['high'].iloc[index],
            'low': self.df['low'].iloc[index],
            'close': self.df['close'].iloc[index],
            'ema_200': self.df['ema_200'].iloc[index] if 'ema_200' in self.df.columns else None
        }
    
    def get_dataframe(self) -> pd.DataFrame:
        """
        Return the full DataFrame.
        
        Returns:
            Copy of the market data DataFrame
        """
        return self.df.copy() if self.df is not None else pd.DataFrame()
    
    def get_candle_count(self) -> int:
        """
        Return total number of candles.
        
        Returns:
            Number of candles in the dataset
        """
        return len(self.df) if self.df is not None else 0


# Quick test function
def test_mt5_data() -> Optional[MT5MarketData]:
    """Test the MT5 data loader"""
    data_path = "data/historical_xauusd_m1.csv"
    
    if not os.path.exists(data_path):
        print("❌ Data file not found. Please export data from MT5 and save as:")
        print(f"   {data_path}")
        print("\nSteps to export from MT5:")
        print("1. Open MT5")
        print("2. Press F2 (History Center)")
        print("3. Select XAUUSD, M1")
        print("4. Click 'Export'")
        print("5. Save to this location")
        return None
    
    market = MT5MarketData(data_path)
    
    if market.load_data():
        market.calculate_ema_mt5()
        
        # Show sample data
        df = market.get_dataframe()
        print("\n📊 Sample data (last 5 rows):")
        print(df[['open', 'high', 'low', 'close', 'ema_200']].tail())
        
        return market
    else:
        return None


if __name__ == "__main__":
    test_mt5_data()
