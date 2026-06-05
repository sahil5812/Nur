import time
import MetaTrader5 as mt5
from datetime import datetime
from core.models import StrategyConfig, RiskConfig
from core.state import StateMachine
from core.risk import RiskManager
from core.strategy import PullbackStrategy
from core.execution import Broker
from data.storage import Storage
from data.data_provider import DataProvider
from utils.logger import logger
from utils.helpers import format_duration
from utils.status_writer import write_status
import shared_state

def load_pending_commands() -> list[dict]:
    from database.db import _raw_conn
    conn = _raw_conn()
    try:
        rows = conn.execute("""
            SELECT id, tenant_id, command, direction, reason 
            FROM manual_commands 
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error(f"Error loading manual commands: {exc}")
        return []
    finally:
        conn.close()

def update_command_status(cmd_id: int, status: str) -> None:
    from database.db import get_connection
    from datetime import datetime
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE manual_commands 
                SET status = ?, executed_at = ? 
                WHERE id = ?
            """, (status, datetime.utcnow().isoformat(), cmd_id))
    except Exception as exc:
        logger.error(f"Error updating command status for command {cmd_id}: {exc}")

def get_user_risk_info(user_id: int) -> dict:
    from database.db import _raw_conn
    conn = _raw_conn()
    try:
        row = conn.execute("SELECT risk_multiplier, display_name FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            return {"risk_multiplier": row["risk_multiplier"], "name": row["display_name"]}
    except Exception as exc:
        logger.error(f"Error getting user risk info: {exc}")
    finally:
        conn.close()
    return {"risk_multiplier": 1.0, "name": f"User {user_id}"}

class TradingEngine:
    def __init__(self):
        # 1. Configs
        self.strat_config = StrategyConfig()
        self.risk_config = RiskConfig()
        
        # 2. Components
        self.storage = Storage()
        self.data_provider = DataProvider()
        self.broker = Broker(self.storage)
        self.risk_manager = RiskManager(self.risk_config, self.storage)
        self.strategy = PullbackStrategy(self.strat_config)
        self.state_machine = StateMachine(self.strat_config.cooldown_seconds)
        
        # 3. Share instances with Telegram thread via shared_state
        shared_state.broker = self.broker
        shared_state.storage = self.storage
        shared_state.engine_state = self.state_machine.current_state
        
        # 4. Loop State
        self.active_ticket = None
        self.last_m1_time = None
        self.pullback_seen = False

    def run(self):
        logger.info("🚀 NUR BOT Trading Engine Starting...")
        
        while not shared_state.shutdown:
            # ── Phase 1: Wait for authentication ──
            if not shared_state.authenticated:
                logger.info("Bot engine waiting for user authentication...")
                while not shared_state.shutdown and not shared_state.authenticated:
                    time.sleep(1.0)
                if shared_state.shutdown:
                    break

            logger.info("User authenticated. Initializing MT5 connection...")
            # Initial connection
            if not self.broker.connect():
                logger.error("❌ Broker initial connection failed. Going back to dormant.")
                time.sleep(5.0)
                continue

            logger.info("🔌 MT5 Connected. Running execution loop...")
            
            while not shared_state.shutdown and shared_state.authenticated:
                try:
                    # ── Check for pending manual commands ──────────────────
                    pending_commands = load_pending_commands()
                    if pending_commands:
                        for cmd in pending_commands:
                            cmd_id = cmd["id"]
                            command = cmd["command"]
                            direction = cmd.get("direction", "")
                            reason = cmd.get("reason", "")
                            user_id_str = cmd.get("tenant_id", "1")
                            try:
                                user_id = int(user_id_str)
                            except ValueError:
                                user_id = 1
                            
                            # Set active user on storage so trades & stats are attributed correctly
                            self.storage.current_user_id = user_id
                            
                            try:
                                if command in ("BUY", "SELL"):
                                    # Fetch current tick and account info
                                    tick = self.data_provider.get_tick(self.strat_config.symbol, force_refresh=True)
                                    acc = mt5.account_info()
                                    m1_rates = self.data_provider.get_rates(
                                        self.strat_config.symbol,
                                        mt5.TIMEFRAME_M1,
                                        self.strat_config.ema_period + self.strat_config.atr_period + 3
                                    )
                                    
                                    if tick and acc and m1_rates:
                                        m1_atr = self.strategy.calculate_atr(m1_rates, self.strat_config.atr_period)
                                        price = tick.ask if command == "BUY" else tick.bid
                                        sl_dist = m1_atr * self.strat_config.sl_atr_multiplier
                                        
                                        user_info = get_user_risk_info(user_id)
                                        risk_mult = user_info["risk_multiplier"]
                                        user_name = user_info["name"]
                                        
                                        # Calculate lot size with risk multiplier
                                        volume = self.risk_manager.calculate_lot_size(acc.balance, m1_atr, self.strat_config.sl_atr_multiplier)
                                        volume = round(max(volume * risk_mult, 0.01), 2)
                                        
                                        order_type = mt5.ORDER_TYPE_BUY if command == "BUY" else mt5.ORDER_TYPE_SELL
                                        
                                        ticket = self.broker.send_order(
                                            self.strat_config.symbol,
                                            order_type,
                                            volume,
                                            sl_dist,
                                            comment=f"NUR SaaS {user_id}",
                                            magic=999999
                                        )
                                        if ticket:
                                            self.active_ticket = ticket
                                            self.state_machine.set_in_trade()
                                            shared_state.engine_state = self.state_machine.current_state
                                            self.pullback_seen = False
                                            
                                            update_command_status(cmd_id, "EXECUTED")
                                            try:
                                                write_status(
                                                    market=self.strat_config.symbol,
                                                    state=self.state_machine.current_state,
                                                    last_close=price,
                                                )
                                            except Exception:
                                                pass
                                            if shared_state.send_message:
                                                shared_state.send_message(f"👤 {user_name} | ✋ Manual {command} Executed\nReason: {reason}")
                                        else:
                                            update_command_status(cmd_id, "FAILED")
                                    else:
                                        logger.warning("⚠️ Manual trade failed: tick, account, or rates info not available.")
                                        update_command_status(cmd_id, "FAILED")
                                        
                                elif command == "CLOSE":
                                    ticket_val = None
                                    if "ticket=" in reason:
                                        try:
                                            ticket_val = int(reason.split("ticket=")[1])
                                        except ValueError:
                                            pass
                                    if ticket_val:
                                        self.broker.close_position(ticket_val, self.strat_config.symbol, "MANUAL_CLOSE")
                                        if self.active_ticket == ticket_val:
                                            self.active_ticket = None
                                            self.state_machine.set_waiting()
                                            shared_state.engine_state = self.state_machine.current_state
                                            self.pullback_seen = False
                                        update_command_status(cmd_id, "EXECUTED")
                                        try:
                                            write_status(
                                                market=self.strat_config.symbol,
                                                state=self.state_machine.current_state,
                                            )
                                        except Exception:
                                            pass
                                        user_info = get_user_risk_info(user_id)
                                        user_name = user_info["name"]
                                        if shared_state.send_message:
                                            shared_state.send_message(f"👤 {user_name} | ✋ Manual CLOSE Executed for Ticket #{ticket_val}")
                                    else:
                                        update_command_status(cmd_id, "FAILED")

                                elif command == "CLOSE_ALL":
                                    closed_count = self.broker.panic_close_all(self.strat_config.symbol)
                                    self.active_ticket = None
                                    self.state_machine.set_waiting()
                                    shared_state.engine_state = self.state_machine.current_state
                                    self.pullback_seen = False
                                    
                                    update_command_status(cmd_id, "EXECUTED")
                                    try:
                                        write_status(
                                            market=self.strat_config.symbol,
                                            state=self.state_machine.current_state,
                                        )
                                    except Exception:
                                        pass
                                    user_info = get_user_risk_info(user_id)
                                    user_name = user_info["name"]
                                    if shared_state.send_message:
                                        shared_state.send_message(f"👤 {user_name} | ✋ Manual CLOSE_ALL Executed\nClosed: {closed_count} positions")
                            except Exception as exc:
                                logger.error(f"Failed to execute manual command {command} for user {user_id}: {exc}")
                                update_command_status(cmd_id, "FAILED")

                    # 🔴 Telegram Pause Toggle
                    if not shared_state.bot_running:
                        time.sleep(0.5)
                        continue
                        
                    # 🔌 Connection Monitor
                    if not self.broker.check_connection():
                        logger.warning("🔌 Connection to MT5 lost. Attempting reconnect...")
                        if not self.broker.reconnect():
                            time.sleep(1.0)
                            continue

                    # Sync State variables with shared state
                    shared_state.engine_state = self.state_machine.current_state

                    # 🚨 Handle Emergency Panic Mode
                    if shared_state.panic_mode:
                        if self.active_ticket:
                            logger.warning("🚨 Panic Mode triggered. Closing active position.")
                            self.broker.panic_close_all(self.strat_config.symbol)
                            self.active_ticket = None
                        self.state_machine.set_waiting()
                        self.pullback_seen = False
                        shared_state.bot_running = False
                        time.sleep(0.5)
                        continue

                    current_state = self.state_machine.current_state

                    # --- FETCH DATA ---
                    m1_rates = self.data_provider.get_rates(
                        self.strat_config.symbol,
                        mt5.TIMEFRAME_M1,
                        self.strat_config.ema_period + self.strat_config.atr_period + 3
                    )
                    m5_rates = self.data_provider.get_rates(
                        self.strat_config.symbol,
                        mt5.TIMEFRAME_M5,
                        self.strat_config.ema_period + 3
                    )
                    h1_rates = self.data_provider.get_rates(
                        self.strat_config.symbol,
                        mt5.TIMEFRAME_H1,
                        self.strat_config.ema_period + 3
                    )

                    if not m1_rates or not m5_rates or not h1_rates:
                        time.sleep(0.5)
                        continue

                    # ── Write engine status to JSON so dashboard reads live state ──
                    try:
                        _m1_closes = [b.close for b in m1_rates]
                        _h1_closes = [b.close for b in h1_rates]
                        _ema200 = self.strategy.calculate_ema(_m1_closes[-self.strat_config.ema_period:], self.strat_config.ema_period)
                        _h1_ema = self.strategy.calculate_ema(_h1_closes[-self.strat_config.ema_period:], self.strat_config.ema_period)
                        _price  = m1_rates[-1].close
                        _trend  = "BULLISH" if _price > _h1_ema else "BEARISH" if _price < _h1_ema else "NONE"
                        write_status(
                            market=self.strat_config.symbol,
                            state=current_state,
                            ema200=_ema200,
                            trend=_trend,
                            last_close=_price,
                        )
                    except Exception:
                        pass  # Non-critical; don't break engine loop

                    # --- STATE 1: WAITING OR COOLDOWN ---
                    if current_state in (StateMachine.STATE_WAITING, StateMachine.STATE_COOLDOWN):
                        # Check if Cooldown is completed
                        if current_state == StateMachine.STATE_COOLDOWN:
                            if not self.state_machine.check_cooldown():
                                time.sleep(0.2)
                                continue

                        # Candle-Close Restriction: strategy signals trigger ONLY on a completed M1 bar
                        last_closed_bar = m1_rates[-2]
                        if self.last_m1_time == last_closed_bar.time:
                            time.sleep(0.2)
                            continue
                        
                        self.last_m1_time = last_closed_bar.time

                        # Check Session filters and Account Risk Daily limits
                        if not self.risk_manager.is_in_trading_session():
                            time.sleep(0.2)
                            continue
                            
                        if not self.risk_manager.check_daily_limits():
                            time.sleep(0.2)
                            continue

                        # Check strategy signals
                        signal, self.pullback_seen, log_msg = self.strategy.check_signals(
                            m1_rates, m5_rates, h1_rates, self.pullback_seen
                        )
                        
                        # Periodic logging of system status
                        logger.info(log_msg)

                        if signal is not None:
                            # Fetch latest tick and account info
                            tick = self.data_provider.get_tick(self.strat_config.symbol, force_refresh=True)
                            acc = mt5.account_info()
                            
                            if tick and acc:
                                price = tick.ask if signal == mt5.ORDER_TYPE_BUY else tick.bid
                                m1_atr = self.strategy.calculate_atr(m1_rates, self.strat_config.atr_period)
                                
                                # Dynamic Lot size
                                volume = self.risk_manager.calculate_lot_size(acc.balance, m1_atr, self.strat_config.sl_atr_multiplier)
                                
                                # Margin check validation
                                if self.risk_manager.check_margin(self.strat_config.symbol, signal, volume, price):
                                    sl_dist = m1_atr * self.strat_config.sl_atr_multiplier
                                    ticket = self.broker.send_order(
                                        self.strat_config.symbol,
                                        signal,
                                        volume,
                                        sl_dist
                                    )
                                    if ticket:
                                        self.active_ticket = ticket
                                        self.state_machine.set_in_trade()
                                        shared_state.engine_state = self.state_machine.current_state
                                        self.pullback_seen = False
                                        
                                        # Send Telegram alerts
                                        t_type = "BUY" if signal == mt5.ORDER_TYPE_BUY else "SELL"
                                        if shared_state.send_message:
                                            shared_state.send_message(
                                                f"📈 *TRADE OPENED*\n"
                                                f"▪️ *Symbol:* {self.strat_config.symbol}\n"
                                                f"▪️ *Type:* {t_type}\n"
                                                f"▪️ *Volume:* {volume} lots\n"
                                                f"▪️ *Price:* ${price:.2f}\n"
                                                f"▪️ *SL:* ${(price - sl_dist) if signal == mt5.ORDER_TYPE_BUY else (price + sl_dist):.2f}"
                                            )
                                else:
                                    logger.warning("⚠️ Insufficient Margin to execute signals.")

                    # --- STATE 2: IN TRADE (REAL-TIME TRAILING STOP MONITOR) ---
                    elif current_state == StateMachine.STATE_IN_TRADE:
                        # Check active positions
                        positions = self.broker.get_positions(self.strat_config.symbol)
                        
                        active_pos = None
                        if positions and self.active_ticket:
                            for p in positions:
                                if p.ticket == self.active_ticket:
                                    active_pos = p
                                    break
                                    
                        if not active_pos:
                            # Position closed externally (SL, TP, or manual client action)
                            logger.info(f"🟢 Position #{self.active_ticket} closed outside engine. Syncing metrics...")
                            close_info = self.broker.sync_closed_position(self.active_ticket)
                            
                            # Enter Cooldown state
                            self.state_machine.set_cooldown()
                            shared_state.engine_state = self.state_machine.current_state
                            self.active_ticket = None
                            self.pullback_seen = False
                            
                            # Telegram alert
                            if close_info and shared_state.send_message:
                                stats = self.storage.get_aggregated_stats()
                                win_rate_str = f"{stats['win_rate']:.1f}%"
                                duration_str = format_duration(close_info["duration"])
                                p_sign = "+" if close_info["profit"] >= 0 else ""
                                
                                shared_state.send_message(
                                    f"💰 *Trade Closed*\n"
                                    f"▪️ *Type:* {close_info['type']}\n"
                                    f"▪️ *Profit:* {p_sign}${close_info['profit']:.2f}\n"
                                    f"▪️ *Duration:* {duration_str}\n"
                                    f"▪️ *Reason:* {close_info['reason']}\n"
                                    f"▪️ *Win Rate:* {win_rate_str}"
                                )
                        else:
                            # Trail Stop-Loss on every iteration/tick
                            tick = self.data_provider.get_tick(self.strat_config.symbol)
                            m1_atr = self.strategy.calculate_atr(m1_rates, self.strat_config.atr_period)
                            
                            if tick and m1_atr > 0:
                                trail_distance = m1_atr * self.strat_config.trail_atr_multiplier
                                
                                if active_pos.type == mt5.ORDER_TYPE_BUY:
                                    new_sl = tick.bid - trail_distance
                                    if active_pos.sl == 0 or new_sl > active_pos.sl:
                                        if self.broker.modify_position_sl(active_pos.ticket, new_sl):
                                            logger.info(f"SL Trailed Up: Long #{active_pos.ticket} SL ➔ {new_sl:.2f}")
                                elif active_pos.type == mt5.ORDER_TYPE_SELL:
                                    new_sl = tick.ask + trail_distance
                                    if active_pos.sl == 0 or new_sl < active_pos.sl:
                                        if self.broker.modify_position_sl(active_pos.ticket, new_sl):
                                            logger.info(f"SL Trailed Down: Short #{active_pos.ticket} SL ➔ {new_sl:.2f}")

                    # Sleep 200ms to allow reactive updates (panic/shutdown etc.)
                    time.sleep(0.2)
                    
                except Exception as e:
                    logger.error(f"❌ Exception in main engine loop: {e}", exc_info=True)
                    time.sleep(1.0)

            # De-authenticated or Shutdown
            logger.info("🔌 Shutting down MT5 API...")
            try:
                mt5.shutdown()
            except Exception:
                pass
            logger.info("✅ MT5 API shut down successfully.")
