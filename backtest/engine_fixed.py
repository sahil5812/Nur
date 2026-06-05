#!/usr/bin/env python3
"""
Fixed Backtesting Engine with proper tracking
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market import MT5MarketData
from core.strategy import TradingStrategy
from core.risk_manager import RiskManager
from core.observer import TradeObserver
from core.tracker import TradeTracker
import pandas as pd
from datetime import datetime

class FixedBacktestEngine:
    """Backtest engine with fixed tracking"""
    
    def __init__(self, config=None):
        self.config = config or {
            'initial_balance': 10000.0,
            'risk_per_trade': 1.0,
            'risk_reward_ratio': 1.5,
            'position_size': 0.01,
            'max_trades_per_day': 5,
            'max_daily_loss': -200.0,
            'commission_per_lot': 3.5,
            'spread': 0.20,
        }
        
        self.market = None
        self.strategy = TradingStrategy()
        self.risk_manager = RiskManager()
        self.tracker = TradeTracker("logs/fixed_backtest.csv")
        
        # State
        self.balance = self.config['initial_balance']
        self.open_trade = None
        self.observer = None
        self.trade_counter = 0
        
    def load_data(self, data_path):
        """Load market data"""
        print(f"📂 Loading data from: {data_path}")
        self.market = MT5MarketData(data_path)
        if not self.market.load_data():
            return False
        if not self.market.calculate_ema_mt5():
            return False
        print(f"✅ Loaded {self.market.get_candle_count()} candles")
        return True
    
    def run(self, start_idx=200, end_idx=None):
        """Run backtest with proper tracking"""
        if self.market is None:
            print("❌ No data loaded")
            return
        
        if end_idx is None:
            end_idx = self.market.get_candle_count()
        
        print(f"\n🚀 Starting Fixed Backtest")
        print(f"   Candles: {start_idx} to {end_idx} ({end_idx - start_idx} total)")
        print(f"   Initial balance: ${self.balance:.2f}")
        print("-" * 60)
        
        for i in range(start_idx, end_idx):
            current = self.market.get_candle(i)
            previous = self.market.get_candle(i-1)
            
            # Manage open trade
            if self.open_trade:
                # Update tracker with current price (THIS WAS MISSING!)
                self.tracker.update_trade(current['close'], current['timestamp'])
                
                # Get observer recommendation
                ema_value = current.get('ema_200')
                observer_exit = self.observer.update(current, ema_value)
                
                # Check exit conditions
                exit_reason = None
                exit_price = current['close']  # Default to current price
                
                # Check SL/TP
                if self.open_trade['direction'] == 'BUY':
                    if current['close'] <= self.open_trade['sl']:
                        exit_reason = "SL hit"
                        exit_price = self.open_trade['sl']
                    elif current['close'] >= self.open_trade['tp']:
                        exit_reason = "TP hit"
                        exit_price = self.open_trade['tp']
                else:  # SELL
                    if current['close'] >= self.open_trade['sl']:
                        exit_reason = "SL hit"
                        exit_price = self.open_trade['sl']
                    elif current['close'] <= self.open_trade['tp']:
                        exit_reason = "TP hit"
                        exit_price = self.open_trade['tp']
                
                # Check observer exit
                if not exit_reason and observer_exit:
                    exit_reason = f"Early: {observer_exit['exit_reason']}"
                    exit_price = observer_exit['exit_price']
                
                # Close trade if needed
                if exit_reason:
                    self._close_trade(exit_price, exit_reason, current['timestamp'])
            
            # Check for new entry (if no open trade)
            if not self.open_trade:
                signal = self.strategy.get_signal(current, previous)
                
                if signal != 'HOLD':
                    self._enter_trade(signal, current, previous)
    
    def _enter_trade(self, signal, current_candle, previous_candle):
        """Enter a new trade"""
        self.trade_counter += 1
        trade_id = f"T{self.trade_counter:03d}"
        
        # Calculate entry with spread
        entry_price = current_candle['close']
        if signal == 'BUY':
            entry_price += self.config['spread'] / 100
        else:
            entry_price -= self.config['spread'] / 100
        
        # Calculate SL/TP
        sl = self.risk_manager.calculate_stop_loss(signal, entry_price, previous_candle)
        tp = self.risk_manager.calculate_take_profit(
            signal, entry_price, sl, 
            risk_reward=self.config['risk_reward_ratio']
        )
        
        # Create open trade record
        self.open_trade = {
            'id': trade_id,
            'direction': signal,
            'entry_price': entry_price,
            'entry_time': current_candle['timestamp'],
            'sl': sl,
            'tp': tp,
            'position_size': self.config['position_size']
        }
        
        # Start observer
        self.observer = TradeObserver()
        self.observer.start_trade(signal, entry_price, current_candle['timestamp'])
        
        # Start tracker
        self.tracker.start_trade(
            trade_id=trade_id,
            direction=signal,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            position_size=self.config['position_size'],
            entry_time=current_candle['timestamp']
        )
        
        print(f"\n🎯 {signal} #{trade_id} at {entry_price:.2f}")
        print(f"   SL: {sl:.2f} | TP: {tp:.2f}")
        print(f"   Risk/Reward: {abs(tp-entry_price)/abs(entry_price-sl):.2f}")
    
    def _close_trade(self, exit_price, exit_reason, exit_time):
        """Close current trade"""
        if not self.open_trade:
            return
        
        # Calculate PnL
        if self.open_trade['direction'] == 'BUY':
            pnl = (exit_price - self.open_trade['entry_price']) * self.open_trade['position_size'] * 100
        else:
            pnl = (self.open_trade['entry_price'] - exit_price) * self.open_trade['position_size'] * 100
        
        # Update balance
        self.balance += pnl
        
        # Close in tracker
        self.tracker.close_trade(exit_price, exit_reason, exit_time)
        
        print(f"  Closed {self.open_trade['direction']}: {exit_reason}, PnL: ${pnl:.2f}")
        
        # Reset
        self.open_trade = None
        self.observer = None
    
    def print_results(self):
        """Print comprehensive results"""
        print("\n" + "="*60)
        print("📊 FIXED BACKTEST RESULTS")
        print("="*60)
        
        stats = self.tracker.get_statistics()
        
        print(f"\n💰 Balance Analysis:")
        print(f"   Initial: ${self.config['initial_balance']:.2f}")
        print(f"   Final: ${self.balance:.2f}")
        print(f"   Net Profit: ${self.balance - self.config['initial_balance']:.2f}")
        print(f"   Return: {((self.balance / self.config['initial_balance']) - 1) * 100:.2f}%")
        
        print(f"\n📊 Trade Statistics:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Expectancy: ${stats['expectancy']:.2f}")
        
        print(f"\n📈 Performance Metrics:")
        print(f"   Average Win: ${stats['avg_win']:.2f}")
        print(f"   Average Loss: ${stats['avg_loss']:.2f}")
        print(f"   Largest Win: ${stats['largest_win']:.2f}")
        print(f"   Largest Loss: ${stats['largest_loss']:.2f}")
        
        # Analyze exit reasons from log file
        self._analyze_exit_reasons()
        
        # Print detailed tracker report
        self.tracker.print_summary_report()
        
        print(f"\n🔧 Configuration:")
        print(f"   Position Size: {self.config['position_size']} lots")
        print(f"   Risk/Reward: {self.config['risk_reward_ratio']}")
        print(f"   Max Daily Trades: {self.config['max_trades_per_day']}")
        print(f"   Spread: {self.config['spread']} pips")
    
    def _analyze_exit_reasons(self):
        """Analyze exit reasons from trade log"""
        try:
            log_file = "logs/fixed_backtest.csv"
            if os.path.exists(log_file):
                df = pd.read_csv(log_file)
                if not df.empty and 'exit_reason' in df.columns:
                    print(f"\n🔍 Exit Reason Analysis:")
                    exit_counts = df['exit_reason'].value_counts()
                    for reason, count in exit_counts.items():
                        percentage = (count / len(df)) * 100
                        print(f"   {reason}: {count} trades ({percentage:.1f}%)")
        except Exception as e:
            print(f"   Could not analyze exit reasons: {e}")


def run_fixed_backtest():
    """Run the fixed backtest"""
    print("🧪 Running Fixed Backtest")
    print("=" * 60)
    
    engine = FixedBacktestEngine()
    
    # Load data
    data_path = "data/historical_xauusd_m1.csv"
    if not engine.load_data(data_path):
        return
    
    # Run on 5000 candles (about 3.5 days)
    engine.run(start_idx=200, end_idx=5200)
    
    # Print results
    engine.print_results()
    
    return engine

if __name__ == "__main__":
    run_fixed_backtest()
