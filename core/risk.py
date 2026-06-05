import MetaTrader5 as mt5
from datetime import datetime, time
from typing import Dict, Any, Optional
from core.models import RiskConfig
from data.storage import Storage
from utils.logger import logger
from utils.helpers import parse_time_offset, is_time_in_range
import shared_state

class RiskManager:
    def __init__(self, config: RiskConfig, storage: Storage):
        self.config = config
        self.storage = storage

    def is_in_trading_session(self) -> bool:
        """
        Validates if current time is within configured London or New York sessions, 
        using the config's timezone offset.
        """
        tz = parse_time_offset(self.config.timezone_offset)
        now_dt = datetime.now(tz)
        
        try:
            lon_start = datetime.strptime(self.config.london_start, "%H:%M").time()
            lon_end = datetime.strptime(self.config.london_end, "%H:%M").time()
            ny_start = datetime.strptime(self.config.ny_start, "%H:%M").time()
            ny_end = datetime.strptime(self.config.ny_end, "%H:%M").time()
        except ValueError as e:
            logger.error(f"❌ Invalid session time format in config: {e}")
            return True # Fallback: allow if config parsing failed
            
        in_london = is_time_in_range(now_dt, lon_start, lon_end, tz)
        in_ny = is_time_in_range(now_dt, ny_start, ny_end, tz)
        
        return in_london or in_ny

    def check_daily_limits(self) -> bool:
        """
        Checks if we have exceeded maximum daily trades or maximum daily loss.
        """
        # First check shared_state flags
        if shared_state.panic_mode or shared_state.hard_stop:
            logger.warning("⚠️ Trading blocked: Panic Mode or Hard Stop is active.")
            return False
            
        if shared_state.soft_stop:
            logger.warning("⚠️ Trading blocked: Soft Stop is active (no new entries).")
            return False

        report = self.storage.get_report_data()
        
        # Today's profit/loss check
        today_profit = report["today_profit"]
        if today_profit <= -self.config.max_daily_loss:
            logger.error(f"❌ Max Daily Loss Limit Hit: Today's PnL is {today_profit:+.2f}$ (Limit: -{self.config.max_daily_loss}$)")
            # Trigger soft stop to stop new trades
            shared_state.soft_stop = True
            return False

        # Max drawdown limit check (total cumulative drawdown)
        agg_stats = self.storage.get_aggregated_stats()
        if agg_stats["max_drawdown"] >= self.config.max_drawdown_limit:
            logger.error(f"❌ Max Drawdown Limit Hit: Max drawdown is {agg_stats['max_drawdown']:.2f}$ (Limit: {self.config.max_drawdown_limit}$)")
            shared_state.soft_stop = True
            return False

        # Daily trades count check
        # Let's count trades taken today
        now = datetime.now()
        today_str = now.date().isoformat()
        with self.storage.lock:
            try:
                conn = self.storage._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM trades WHERE entry_time >= ?", 
                    (today_str + "T00:00:00",)
                )
                today_trades = cursor.fetchone()[0] or 0
                conn.close()
            except Exception as e:
                logger.error(f"Failed to count today's trades: {e}")
                today_trades = 0

        if today_trades >= self.config.max_trades_per_day:
            logger.warning(f"⚠️ Max Daily Trade Limit Hit: {today_trades} trades taken today (Limit: {self.config.max_trades_per_day})")
            return False

        return True

    def calculate_lot_size(self, balance: float, atr: float, sl_atr_multiplier: float) -> float:
        """
        Calculates lot size based on account balance, risk percent, and SL distance.
        Formula: risk_amount / (sl_distance * 100) for gold (1 lot = 100 oz).
        """
        risk_amount = balance * (self.config.risk_percent / 100.0)
        sl_distance = atr * sl_atr_multiplier
        
        if sl_distance <= 0:
            return 0.01

        # Standard gold calculation: 1 lot = 100 value per point.
        lot = risk_amount / (sl_distance * 100.0)
        # Standard limits for lots (min 0.01)
        lot = round(max(lot, 0.01), 2)
        return lot

    def check_margin(self, symbol: str, order_type: int, volume: float, price: float) -> bool:
        """
        Performs MT5 order checks to ensure we have sufficient margin.
        """
        account = mt5.account_info()
        if account is None:
            logger.error("❌ Failed to fetch account info for margin check.")
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        try:
            check_result = mt5.order_check(request)
            if check_result is None:
                logger.error("❌ MT5 order_check returned None")
                return False
                
            if check_result.retcode != 0:
                logger.error(f"❌ Margin check failed (retcode={check_result.retcode}): {check_result.comment}")
                return False

            required_margin = check_result.margin
            free_margin = account.free_margin
            
            # Check with a 10% buffer
            if free_margin < (required_margin * 1.1):
                logger.error(f"❌ Insufficient Margin: Free: {free_margin:.2f}$, Required: {required_margin:.2f}$ (+10% buffer)")
                return False
                
            return True
        except Exception as e:
            logger.error(f"❌ Exception during margin check: {e}")
            return False
