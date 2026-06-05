#!/usr/bin/env python3
"""
Trade Tracker - Logs and analyzes all trade performance.

Tracks exactly what you asked for:
- Total trades
- Profitable trades (TP hit)
- Trades hit SL
- Trades closed without TP
- Net profit
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
from typing import Optional, Dict, Any, List, Tuple


class TradeTracker:
    """
    Tracks and analyzes trade performance.
    
    Maintains a log of all trades with detailed statistics including
    PnL, win rate, profit factor, and exit reasons.
    """
    
    def __init__(self, log_file: str = "logs/trades_log.csv") -> None:
        """
        Initialize trade tracker.
        
        Args:
            log_file: Path to CSV file for logging trades
        """
        self.log_file: str = log_file
        self.trades: List[Dict[str, Any]] = []
        self.current_trade: Optional[Dict[str, Any]] = None
        
        # Initialize log file if it doesn't exist
        self._init_log_file()
    
    def _init_log_file(self) -> None:
        """Initialize the log file with headers"""
        if not os.path.exists(self.log_file):
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            
            headers = [
                'trade_id', 'entry_time', 'exit_time', 'duration_minutes',
                'direction', 'entry_price', 'exit_price', 'stop_loss', 'take_profit',
                'exit_reason', 'pnl', 'pnl_pct', 'risk_reward_achieved',
                'max_profit_pct', 'max_loss_pct', 'candles_in_trade',
                'position_size', 'commission', 'swap', 'net_pnl'
            ]
            
            pd.DataFrame(columns=headers).to_csv(self.log_file, index=False)
            print(f"📝 Initialized trade log: {self.log_file}")
    
    def start_trade(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: float = 0.01,
        entry_time: Optional[datetime] = None
    ) -> None:
        """
        Start tracking a new trade.
        
        Args:
            trade_id: Unique identifier for the trade
            direction: 'BUY' or 'SELL'
            entry_price: Entry price of the trade
            stop_loss: Stop loss price
            take_profit: Take profit price
            position_size: Position size in lots (default: 0.01)
            entry_time: Entry timestamp (default: current time)
        """
        self.current_trade = {
            'trade_id': trade_id,
            'entry_time': entry_time or datetime.now(),
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'max_profit_pct': 0,
            'max_loss_pct': 0,
            'candles_in_trade': 0,
            'commission': 0,  # Could calculate based on broker
            'swap': 0,        # Could calculate based on holding time
            'history': []     # Price history during trade
        }
        
        print(f"📊 Started tracking trade {trade_id}: {direction} at {entry_price:.2f}")
    
    def update_trade(
        self,
        current_price: float,
        current_time: Optional[datetime] = None
    ) -> Tuple[float, float]:
        """
        Update current trade with latest price.
        
        Args:
            current_price: Current market price
            current_time: Current timestamp (default: current time)
            
        Returns:
            Tuple of (pnl, pnl_pct)
        """
        if not self.current_trade:
            return 0.0, 0.0
        
        self.current_trade['candles_in_trade'] += 1
        
        # Calculate current PnL
        if self.current_trade['direction'] == 'BUY':
            pnl: float = (current_price - self.current_trade['entry_price']) * self.current_trade['position_size'] * 100
            pnl_pct: float = (current_price - self.current_trade['entry_price']) / self.current_trade['entry_price'] * 100
        else:  # SELL
            pnl = (self.current_trade['entry_price'] - current_price) * self.current_trade['position_size'] * 100
            pnl_pct = (self.current_trade['entry_price'] - current_price) / self.current_trade['entry_price'] * 100
        
        # Update max profit/loss
        self.current_trade['max_profit_pct'] = max(self.current_trade['max_profit_pct'], pnl_pct)
        self.current_trade['max_loss_pct'] = min(self.current_trade['max_loss_pct'], pnl_pct)
        
        # Add to history
        self.current_trade['history'].append({
            'timestamp': current_time or datetime.now(),
            'price': current_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
        
        return pnl, pnl_pct
    
    def close_trade(
        self,
        exit_price: float,
        exit_reason: str,
        exit_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Close the current trade and log it.
        
        Args:
            exit_price: Exit price of the trade
            exit_reason: Reason for closing the trade
            exit_time: Exit timestamp (default: current time)
            
        Returns:
            Trade record dictionary or None if no active trade
        """
        if not self.current_trade:
            print("❌ No active trade to close")
            return None
        
        # Calculate final PnL
        if self.current_trade['direction'] == 'BUY':
            pnl: float = (exit_price - self.current_trade['entry_price']) * self.current_trade['position_size'] * 100
            pnl_pct: float = (exit_price - self.current_trade['entry_price']) / self.current_trade['entry_price'] * 100
        else:  # SELL
            pnl = (self.current_trade['entry_price'] - exit_price) * self.current_trade['position_size'] * 100
            pnl_pct = (self.current_trade['entry_price'] - exit_price) / self.current_trade['entry_price'] * 100
        
        # Calculate risk/reward achieved
        entry: float = self.current_trade['entry_price']
        sl: float = self.current_trade['stop_loss']
        tp: Optional[float] = self.current_trade['take_profit']
        
        if self.current_trade['direction'] == 'BUY':
            risk: float = entry - sl
            reward: float = tp - entry if tp else 0
        else:  # SELL
            risk = sl - entry
            reward = entry - tp if tp else 0
        
        risk_reward_achieved: float = 0
        if risk > 0:
            if self.current_trade['direction'] == 'BUY':
                reward_achieved: float = exit_price - entry
            else:
                reward_achieved = entry - exit_price
            risk_reward_achieved = reward_achieved / risk
        
        # Calculate net PnL (including commission and swap)
        net_pnl: float = pnl - self.current_trade['commission'] + self.current_trade['swap']
        
        # Calculate duration
        exit_time = exit_time or datetime.now()
        duration: float = (exit_time - self.current_trade['entry_time']).total_seconds() / 60
        
        # Create trade record
        trade_record: Dict[str, Any] = {
            'trade_id': self.current_trade['trade_id'],
            'entry_time': self.current_trade['entry_time'],
            'exit_time': exit_time,
            'duration_minutes': round(duration, 2),
            'direction': self.current_trade['direction'],
            'entry_price': self.current_trade['entry_price'],
            'exit_price': exit_price,
            'stop_loss': self.current_trade['stop_loss'],
            'take_profit': self.current_trade['take_profit'],
            'exit_reason': exit_reason,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'risk_reward_achieved': round(risk_reward_achieved, 2),
            'max_profit_pct': round(self.current_trade['max_profit_pct'], 2),
            'max_loss_pct': round(self.current_trade['max_loss_pct'], 2),
            'candles_in_trade': self.current_trade['candles_in_trade'],
            'position_size': self.current_trade['position_size'],
            'commission': self.current_trade['commission'],
            'swap': self.current_trade['swap'],
            'net_pnl': round(net_pnl, 2)
        }
        
        # Add to trades list
        self.trades.append(trade_record)
        
        # Save to CSV
        self._save_to_csv(trade_record)
        
        # Print summary
        self._print_trade_summary(trade_record)
        
        # Clear current trade
        self.current_trade = None
        
        return trade_record
    
    def _save_to_csv(self, trade_record: Dict[str, Any]) -> None:
        """
        Save trade record to CSV file.
        
        Args:
            trade_record: Dictionary with trade data
        """
        try:
            df = pd.DataFrame([trade_record])
            df.to_csv(self.log_file, mode='a', header=False, index=False)
        except Exception as e:
            print(f"❌ Error saving trade to CSV: {e}")
    
    def _print_trade_summary(self, trade: Dict[str, Any]) -> None:
        """
        Print a summary of the closed trade.
        
        Args:
            trade: Trade record dictionary
        """
        color = '🟢' if trade['pnl'] > 0 else '🔴'
        
        print(f"\n{color} Trade {trade['trade_id']} Closed {color}")
        print(f"   Direction: {trade['direction']}")
        print(f"   Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f}")
        print(f"   PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
        print(f"   Reason: {trade['exit_reason']}")
        print(f"   Duration: {trade['duration_minutes']:.1f} min, {trade['candles_in_trade']} candles")
        print(f"   Max Profit: {trade['max_profit_pct']:.2f}%, Max Loss: {trade['max_loss_pct']:.2f}%")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Calculate and return trade statistics.
        
        Returns:
            Dictionary with comprehensive trade statistics
        """
        if not self.trades:
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'profit_factor': 0,
                'expectancy': 0
            }
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(self.trades)
        
        # Basic statistics
        total_trades: int = len(df)
        profitable_trades: int = len(df[df['pnl'] > 0])
        losing_trades: int = len(df[df['pnl'] <= 0])
        win_rate: float = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        # PnL statistics
        total_pnl: float = df['pnl'].sum()
        avg_pnl: float = df['pnl'].mean()
        
        winning_trades = df[df['pnl'] > 0]
        losing_trades_df = df[df['pnl'] <= 0]
        
        avg_win: float = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss: float = losing_trades_df['pnl'].mean() if len(losing_trades_df) > 0 else 0
        
        largest_win: float = df['pnl'].max()
        largest_loss: float = df['pnl'].min()
        
        # Advanced metrics
        gross_profit: float = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        gross_loss: float = abs(losing_trades_df['pnl'].sum()) if len(losing_trades_df) > 0 else 0
        
        profit_factor: float = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)
        win_percentage: float = profitable_trades / total_trades if total_trades > 0 else 0
        loss_percentage: float = losing_trades / total_trades if total_trades > 0 else 0
        expectancy: float = (win_percentage * avg_win) - (loss_percentage * abs(avg_loss))
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'largest_win': round(largest_win, 2),
            'largest_loss': round(largest_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2)
        }
    
    def print_summary_report(self) -> None:
        """Print a comprehensive summary report"""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("📊 NUR TRADE PERFORMANCE SUMMARY")
        print("="*60)
        
        print(f"\n📈 Trade Statistics:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Profitable: {stats['profitable_trades']} ({stats['win_rate']}%)")
        print(f"   Losing: {stats['losing_trades']} ({100 - stats['win_rate']:.1f}%)")
        
        print(f"\n💰 PnL Analysis:")
        print(f"   Total PnL: ${stats['total_pnl']:.2f}")
        print(f"   Average PnL: ${stats['avg_pnl']:.2f}")
        print(f"   Average Win: ${stats['avg_win']:.2f}")
        print(f"   Average Loss: ${stats['avg_loss']:.2f}")
        print(f"   Largest Win: ${stats['largest_win']:.2f}")
        print(f"   Largest Loss: ${stats['largest_loss']:.2f}")
        
        print(f"\n📊 Performance Metrics:")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Expectancy: ${stats['expectancy']:.2f}")
        
        if stats['total_trades'] > 0:
            # Analyze exit reasons
            df = pd.DataFrame(self.trades)
            exit_reasons = df['exit_reason'].value_counts()
            
            print(f"\n🔍 Exit Reason Analysis:")
            for reason, count in exit_reasons.items():
                percentage = (count / stats['total_trades']) * 100
                print(f"   {reason}: {count} trades ({percentage:.1f}%)")
        
        print("\n" + "="*60)
    
    def save_detailed_report(self, filename: str = "logs/trade_analysis_report.json") -> None:
        """
        Save detailed report to JSON file.
        
        Args:
            filename: Path to output JSON file
        """
        report = {
            'summary': self.get_statistics(),
            'trades': self.trades,
            'generated_at': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📄 Detailed report saved to: {filename}")


# Test the tracker
def test_tracker() -> None:
    """Test trade tracker functionality"""
    print("🧪 Testing Trade Tracker")
    print("=" * 50)
    
    tracker = TradeTracker("logs/test_trades_log.csv")
    
    # Simulate some trades
    print("\n1. Simulating BUY trade (profitable):")
    tracker.start_trade(
        trade_id=1,
        direction='BUY',
        entry_price=2050.00,
        stop_loss=2048.00,
        take_profit=2054.00,
        position_size=0.1
    )
    
    # Update trade a few times
    tracker.update_trade(2051.00)
    tracker.update_trade(2052.00)
    tracker.update_trade(2053.50)
    
    # Close with profit
    trade1 = tracker.close_trade(
        exit_price=2053.80,
        exit_reason="TP hit"
    )
    
    print("\n2. Simulating SELL trade (loss):")
    tracker.start_trade(
        trade_id=2,
        direction='SELL',
        entry_price=2050.00,
        stop_loss=2052.50,
        take_profit=2046.00,
        position_size=0.05
    )
    
    tracker.update_trade(2051.00)
    tracker.update_trade(2052.20)
    
    # Close with loss
    trade2 = tracker.close_trade(
        exit_price=2052.45,
        exit_reason="SL hit"
    )
    
    print("\n3. Simulating BUY trade (early exit):")
    tracker.start_trade(
        trade_id=3,
        direction='BUY',
        entry_price=2050.00,
        stop_loss=2048.00,
        take_profit=2054.00,
        position_size=0.02
    )
    
    tracker.update_trade(2049.50)
    tracker.update_trade(2049.00)
    
    # Close early
    trade3 = tracker.close_trade(
        exit_price=2049.20,
        exit_reason="Early exit - EMA crossback"
    )
    
    # Print summary
    tracker.print_summary_report()
    
    # Save report
    tracker.save_detailed_report("logs/test_report.json")

if __name__ == "__main__":
    test_tracker()
