"""
data/storage.py — Trade storage adapter for the core engine.

Connects to the MAIN application database (database/db.py) so that
trades logged by the engine are visible in the dashboard.

Column mapping (engine → main DB):
  trade_type → direction
  volume     → lot
  profit     → pnl
  (added)    → user_id, is_paper
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from utils.logger import logger
from utils.helpers import safe_divide


class Storage:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_user_id = 1  # Default user; set per-command for SaaS

    def _get_connection(self):
        """Get connection to the main application database."""
        from database.db import _raw_conn
        return _raw_conn()

    def init_db(self):
        """No-op — main database schema is managed by database/db.py."""
        pass

    def save_open_trade(self, ticket: int, symbol: str, trade_type: str, volume: float,
                        requested_price: float, entry_price: float, sl: float, tp: float,
                        entry_time: datetime, user_id: int = None,
                        session: str = None, regime: str = None) -> bool:
        """
        Logs a newly opened position to the main trades table.
        """
        import config

        if user_id is None:
            user_id = self.current_user_id

        direction = "BUY" if trade_type.upper() in ("BUY", "ORDER_TYPE_BUY", "0") else "SELL"
        is_paper = 1 if config.PAPER_TRADING else 0

        if not session:
            # Determine timezone-aware session (hour of day)
            from datetime import timezone
            hour = datetime.now(timezone.utc).hour
            if 7 <= hour < 16:
                session = "LONDON"
            elif 12 <= hour < 21:
                session = "NY"
            else:
                session = "ASIAN"

        if not regime:
            regime = "TRENDING"

        with self.lock:
            try:
                conn = self._get_connection()
                conn.execute("""
                    INSERT INTO trades (
                        user_id, ticket, direction, entry_price,
                        sl, tp, lot, is_paper, entry_time, session, regime
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, str(ticket), direction, entry_price,
                    sl, tp, volume, is_paper, entry_time.isoformat(), session, regime
                ))
                conn.commit()
                conn.close()
                logger.info(f"💾 Logged open trade: #{ticket} {direction} {volume} lots on {symbol}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to save open trade to DB: {e}")
                return False

    def close_trade(self, ticket: int, exit_price: float, profit: float,
                    exit_time: datetime, exit_reason: str, current_balance: float = 10000.0) -> bool:
        """
        Updates an existing trade with exit info and refreshes bot_stats for the dashboard.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                conn.execute("""
                    UPDATE trades SET
                        exit_price = ?,
                        pnl = ?,
                        exit_time = ?,
                        exit_reason = ?
                    WHERE ticket = ?
                """, (exit_price, profit, exit_time.isoformat(), exit_reason, str(ticket)))
                conn.commit()
                conn.close()
                logger.info(f"💾 Updated closed trade: #{ticket} Profit: {profit:+.2f}$ Reason: {exit_reason}")
            except Exception as e:
                logger.error(f"❌ Failed to update closed trade in DB: {e}")
                return False

        # Update bot_stats table so dashboard KPIs refresh immediately
        try:
            from database.stats_db import update_stats
            update_stats(profit, user_id=self.current_user_id)
        except Exception as stats_err:
            logger.error(f"❌ Failed to update bot_stats: {stats_err}")

        return True

    # ─── Aggregate queries (used by engine & risk manager) ─────────

    def get_aggregated_stats(self) -> Dict[str, Any]:
        """
        Computes Sharpe Ratio, Profit Factor, Recovery Factor, Drawdown, etc.
        from the main trades table.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trades
                    WHERE exit_time IS NOT NULL AND user_id = ?
                    ORDER BY exit_time ASC
                """, (self.current_user_id,))
                rows = cursor.fetchall()
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching stats from DB: {e}")
                return self._empty_stats()

        total_trades = len(rows)
        if total_trades == 0:
            return self._empty_stats()

        wins = 0
        losses = 0
        total_profit = 0.0
        gross_profits = 0.0
        gross_losses = 0.0
        equity_curve = [0.0]
        cumulative = 0.0

        for r in rows:
            p = r["pnl"] or 0.0
            total_profit += p
            cumulative += p
            equity_curve.append(cumulative)

            if p > 0:
                wins += 1
                gross_profits += p
            else:
                losses += 1
                gross_losses += abs(p)

        win_rate = safe_divide(wins, total_trades) * 100.0
        avg_profit_loss = safe_divide(total_profit, total_trades)
        profit_factor = safe_divide(
            gross_profits, gross_losses,
            default=float('inf') if gross_profits > 0 else 0.0
        )

        # Max Drawdown calculation
        max_dd = 0.0
        peak = -999999.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd

        recovery_factor = safe_divide(total_profit, max_dd, default=0.0)

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "avg_profit_loss": avg_profit_loss,
            "max_drawdown": max_dd,
            "profit_factor": profit_factor,
            "recovery_factor": recovery_factor,
        }

    def get_report_data(self) -> Dict[str, Any]:
        """
        Compiles standard Daily, Weekly metrics & recent trades for Telegram commands.
        """
        stats = self.get_aggregated_stats()

        now = datetime.now()
        today_str = now.date().isoformat()
        one_week_ago = (now - timedelta(days=7)).isoformat()

        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Today's profit
                cursor.execute(
                    "SELECT SUM(pnl) FROM trades WHERE exit_time >= ? AND exit_time IS NOT NULL AND user_id = ?",
                    (today_str + "T00:00:00", self.current_user_id)
                )
                today_profit = cursor.fetchone()[0] or 0.0

                # Weekly profit
                cursor.execute(
                    "SELECT SUM(pnl) FROM trades WHERE exit_time >= ? AND exit_time IS NOT NULL AND user_id = ?",
                    (one_week_ago, self.current_user_id)
                )
                weekly_profit = cursor.fetchone()[0] or 0.0

                # Last 5 trades
                cursor.execute("""
                    SELECT ticket, direction, lot, pnl, exit_time, exit_reason
                    FROM trades
                    WHERE exit_time IS NOT NULL AND user_id = ?
                    ORDER BY exit_time DESC LIMIT 5
                """, (self.current_user_id,))
                last_5_rows = cursor.fetchall()
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching report statistics: {e}")
                today_profit = 0.0
                weekly_profit = 0.0
                last_5_rows = []

        last_5 = []
        for r in last_5_rows:
            last_5.append({
                "ticket": r["ticket"],
                "symbol": "XAUUSD",
                "type": r["direction"],
                "volume": r["lot"],
                "profit": r["pnl"],
                "reason": r["exit_reason"],
            })

        return {
            "today_profit": today_profit,
            "weekly_profit": weekly_profit,
            "total_trades": stats["total_trades"],
            "win_rate": stats["win_rate"],
            "total_profit": stats["total_profit"],
            "max_drawdown": stats["max_drawdown"],
            "last_5": last_5,
        }

    @staticmethod
    def _empty_stats():
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_profit": 0.0,
            "avg_profit_loss": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "recovery_factor": 0.0,
        }
