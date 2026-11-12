import time
import MetaTrader5 as mt5
from datetime import datetime
from typing import List, Optional, Any
from core.models import Tick
from data.storage import Storage
from utils.logger import logger
import shared_state

class Broker:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.deviation = 20

    def connect(self) -> bool:
        """
        Initializes MT5 connection. If it fails, attempts reconnection 
        using exponential backoff.
        """
        if mt5.initialize():
            logger.info(f"✅ MT5 Initialized successfully | Version: {mt5.__version__}")
            return True

        logger.error("❌ MT5 initial connection failed. Entering exponential backoff...")
        return self.reconnect()

    def reconnect(self) -> bool:
        """
        Implements Exponential Backoff strategy for MT5 reconnection.
        """
        backoff = 1.0
        max_backoff = 60.0

        while not shared_state.shutdown:
            logger.info(f"🔄 Retrying MT5 connection in {backoff} seconds...")
            # Sleep in small increments to remain interruptible during shutdown
            start_sleep = time.time()
            while time.time() - start_sleep < backoff:
                if shared_state.shutdown:
                    return False
                time.sleep(0.1)

            # Shutdown check
            if shared_state.shutdown:
                return False

            if mt5.initialize():
                logger.info("🔌 MT5 Reconnection successful!")
                return True

            backoff = min(backoff * 2.0, max_backoff)

        return False

    def check_connection(self) -> bool:
        """
        Verifies connection health.
        """
        info = mt5.terminal_info()
        if info is None or not info.connected:
            return False
        return True

    def get_latency(self) -> float:
        """
        Calculates MT5 API round-trip latency in milliseconds.
        """
        start = time.time()
        mt5.terminal_info()
        return (time.time() - start) * 1000.0

    def get_positions(self, symbol: str) -> List[Any]:
        """
        Fetches all open positions for the given symbol.
        """
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            # None might be returned on error
            err = mt5.last_error()
            if err[0] != mt5.RES_OK:
                logger.error(f"❌ Failed to get positions: {err}")
            return []
        return list(positions)

    def send_order(self, symbol: str, order_type: int, volume: float, sl_distance: float, comment: Optional[str] = None, magic: int = 123456) -> Optional[int]:
        """
        Sends order with retries. Returns position ticket if successful.
        Tracks slippage (requested vs filled price) and logs open trade to DB.
        """
        # Ensure we are connected
        if not self.check_connection():
            logger.error("❌ Cannot send order: Broker is disconnected.")
            if not self.reconnect():
                return None

        # Fetch current tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error("❌ Cannot send order: Failed to fetch tick.")
            return None

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        # Calculate SL
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = price - sl_distance
            trade_type_str = "BUY"
        else:
            sl = price + sl_distance
            trade_type_str = "SELL"
            
        # Hard round sl
        sl = round(sl, 2)

        if comment is None:
            comment = f"NUR SaaS {self.storage.current_user_id}"

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "deviation": self.deviation,
            "comment": comment,
            "magic": magic,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Order retry loop (up to 3 times)
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            logger.info(f"📤 Sending {trade_type_str} order ({volume} lot) - Attempt {attempt}/{max_retries}...")
            
            result = mt5.order_send(request)
            if result is None:
                logger.error("❌ order_send returned None")
                time.sleep(0.5)
                continue

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # SUCCESS
                ticket = result.order
                fill_price = result.price
                
                logger.info(f"✅ Order Executed. Ticket: #{ticket} | Fill Price: {fill_price:.2f} | SL: {sl:.2f}")
                
                # Save open trade to SQLite
                self.storage.save_open_trade(
                    ticket=ticket,
                    symbol=symbol,
                    trade_type=trade_type_str,
                    volume=volume,
                    requested_price=price,
                    entry_price=fill_price,
                    sl=sl,
                    tp=0.0, # TP is 0 as we trail SL
                    entry_time=datetime.now()
                )
                
                return ticket
            else:
                logger.error(f"❌ Order failed: Retcode {result.retcode} ({result.comment})")
                
                # Check if error is transient, if not break early
                if result.retcode in (mt5.TRADE_RETCODE_REJECT, mt5.TRADE_RETCODE_INVALID):
                    logger.error("❌ Order rejected as invalid, aborting retries.")
                    break
                    
                time.sleep(0.5)

        return None

    def close_position(self, ticket: int, symbol: str, exit_reason: str) -> bool:
        """
        Closes a specific position by ticket, retrieves real deal stats, 
        and updates the database.
        """
        # Find position to close
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            logger.warning(f"⚠️ Position #{ticket} not found to close.")
            return False
            
        pos = positions[0]
        volume = pos.volume
        pos_type = pos.type
        
        # Determine opposite order type
        close_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"❌ Failed to fetch current tick for closing position #{ticket}")
            return False
            
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": self.deviation,
            "comment": f"NUR CLOSE: {exit_reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            logger.info(f"📤 Closing position #{ticket} - Attempt {attempt}/{max_retries}...")
            result = mt5.order_send(request)
            
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Position #{ticket} closed successfully.")
                
                # Wait for MT5 trade history to sync before fetching details
                time.sleep(0.5)
                
                # Query history deals
                deals = mt5.history_deals_get(position=ticket)
                exit_price = result.price
                profit = pos.profit
                
                if deals:
                    # Look for exit deal (entry == 1 (DEAL_ENTRY_OUT))
                    exit_deal = None
                    for d in deals:
                        if d.entry == 1:
                            exit_deal = d
                            break
                    if exit_deal is None:
                        exit_deal = deals[-1] # Fallback
                        
                    exit_price = float(exit_deal.price)
                    # Total net profit = profit + commission + swap
                    profit = float(exit_deal.profit) + float(exit_deal.commission) + float(exit_deal.swap)
                
                account = mt5.account_info()
                balance = account.balance if account else 10000.0
                
                # Save exit to DB
                self.storage.close_trade(
                    ticket=ticket,
                    exit_price=exit_price,
                    profit=profit,
                    exit_time=datetime.now(),
                    exit_reason=exit_reason,
                    current_balance=balance
                )
                return True
                
            logger.error(f"❌ Failed to close position #{ticket}: Retcode {result.retcode if result else 'None'}")
            time.sleep(0.5)

        return False

    def modify_position_sl(self, ticket: int, new_sl: float) -> bool:
        """
        Modifies Stop Loss for a running position.
        """
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": round(new_sl, 2),
        }
        
        result = mt5.order_send(request)
        if result is None:
            return False
            
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return True
            
        return False

    def sync_closed_position(self, ticket: int, default_reason: str = "SL/TP Hit") -> Optional[dict]:
        """
        Synchronizes a position that was closed externally (SL, TP, or manual action).
        Queries trade history, computes final metrics, writes to DB, and returns details.
        """
        # Wait a moment for history to update
        time.sleep(0.5)
        
        deals = mt5.history_deals_get(position=ticket)
        if not deals or len(deals) == 0:
            logger.warning(f"⚠️ No history deals found for position #{ticket}")
            return None
            
        exit_deal = None
        # Entry deal is where entry == 0 (DEAL_ENTRY_IN)
        # Exit deal is where entry == 1 (DEAL_ENTRY_OUT)
        for d in deals:
            if d.entry == 1: # DEAL_ENTRY_OUT
                exit_deal = d
                break
                
        if not exit_deal:
            # Fallback to the last deal if we couldn't find DEAL_ENTRY_OUT specifically
            exit_deal = deals[-1]
            
        exit_reason = default_reason
        reason_code = getattr(exit_deal, "reason", -1)
        
        # MT5 Deal Reason mapping
        # 0 = CLIENT, 1 = MOBILE, 2 = WEB, 3 = EXPERT, 4 = SL, 5 = TP, 6 = SO
        if reason_code == 4:
            exit_reason = "SL Hit"
        elif reason_code == 5:
            exit_reason = "TP Hit"
        elif reason_code == 6:
            exit_reason = "Stop Out"
        elif reason_code in (0, 1, 2):
            exit_reason = f"Manual ({['Desktop', 'Mobile', 'Web'][reason_code]})"
        elif reason_code == 3:
            exit_reason = "Closed by Bot"
            
        exit_price = float(exit_deal.price)
        profit = float(exit_deal.profit) + float(exit_deal.commission) + float(exit_deal.swap)
        
        # Calculate duration
        entry_time = deals[0].time
        exit_time = exit_deal.time
        duration = float(max(exit_time - entry_time, 0))
        
        account = mt5.account_info()
        balance = account.balance if account else 10000.0
        
        self.storage.close_trade(
            ticket=ticket,
            exit_price=exit_price,
            profit=profit,
            exit_time=datetime.now(),
            exit_reason=exit_reason,
            current_balance=balance
        )
        
        # Return summary info
        return {
            "ticket": ticket,
            "type": "BUY" if exit_deal.type == mt5.DEAL_TYPE_SELL else "SELL", # Opposite of close deal type
            "profit": profit,
            "duration": duration,
            "reason": exit_reason
        }

    def panic_close_all(self, symbol: str) -> int:
        """
        Emergency liquidation of all positions for the given symbol.
        """
        positions = self.get_positions(symbol)
        closed_count = 0
        
        for pos in positions:
            if self.close_position(pos.ticket, symbol, "PANIC_LIQUIDATION"):
                closed_count += 1
                
        return closed_count
