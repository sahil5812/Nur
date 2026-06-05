"""
bot_engine.py — Nur Trading Bot Core Engine (Phase 2 — Intelligence Layer)

Phase 2 additions over Phase 1:
  - H4 timeframe bias (3-TF: H4 bias → H1 confirm → M1 entry)
  - RSI(14) filter fed into calculate_score()
  - MACD(12,26,9) confirmation fed into calculate_score()
  - Market regime detection (TRENDING/RANGING/BREAKOUT/HIGH_VOLATILITY)
  - Regime-adaptive score thresholds
  - News filter (NFP/CPI/FOMC blackout windows)
  - Session name tagging on every trade log
  - EMA history buffer for regime detection
"""

import time
from datetime import datetime, timezone

# ─── Lazy-loaded module references (populated by _lazy_init) ──
# These are set to None at module level and populated once main() runs.
# This prevents heavy imports (MT5 DLLs, torch, numpy, stable_baselines3)
# from blocking the application's startup sequence.
mt5 = None
config = None
shared_state = None

update_stats = load_stats = check_daily_lock = check_profit_lock = log_trade = None
calculate_score = None
trading_session_open = None
spread_ok = None
write_status = None
connect_mt5 = ensure_connected = None
calculate_rsi = None
calculate_macd = None
detect_regime = get_threshold = None
REGIME_LABELS = None
is_news_window = None

logger = None
trade_log = None

# ─── State machine ────────────────────────────────────────────
STATE_WAITING  = "WAITING"
STATE_IN_TRADE = "IN_TRADE"
STATE_COOLDOWN = "COOLDOWN"
TREND_NONE     = "NONE"
TREND_BULLISH  = "BULLISH"
TREND_BEARISH  = "BEARISH"

# Global fallback placeholders for backward compatibility
state             = STATE_WAITING
trend             = TREND_NONE
pullback_seen     = False
last_trade_time   = None
last_candle_time  = None
last_known_profit = 0.0

# Dynamic isolated user states map (multi-tenant SaaS)
_user_states = {}

# Trade metadata (for logging)
_current_score       = 0
_current_entry_price = 0.0
_current_sl          = 0.0
_current_lot         = 0.0
_entry_time: str | None = None
_current_regime      = "TRENDING"

# EMA history for regime detection
_ema_history: list[float] = []
_atr_history: list[float] = []

# Paper trader & RL agent (lazy-initialized)
_paper = None
_rl_agent = None

# ─── Constants (set after config loads) ───────────────────────
SYMBOL = SLEEP_TIME = COOLDOWN_SECONDS = DEVIATION = None
EMA_MIN_BUFFER = ATR_MULTIPLIER = TRAIL_ATR_MULT = SL_ATR_MULT = None
RISK_PERCENT = DAILY_LOSS_LIMIT = DAILY_PROFIT_TARGET = None
MAX_TRADES_PER_DAY = MIN_SCORE = EMA_PERIOD = ATR_PERIOD = None
M1_TF = H1_TF = H4_TF = None

_initialized = False


def _lazy_init():
    """
    Import all heavy modules and set up constants.
    Called ONCE at the start of main() — never at module import time.
    This keeps 'from bot_engine import main' extremely fast.
    """
    global mt5, config, shared_state, _initialized
    global update_stats, load_stats, check_daily_lock, check_profit_lock, log_trade
    global calculate_score, trading_session_open, spread_ok, write_status
    global connect_mt5, ensure_connected
    global calculate_rsi, calculate_macd
    global detect_regime, get_threshold, REGIME_LABELS, is_news_window
    global logger, trade_log
    global _paper, _rl_agent
    global SYMBOL, M1_TF, H1_TF, H4_TF, EMA_PERIOD, ATR_PERIOD
    global SLEEP_TIME, COOLDOWN_SECONDS, DEVIATION
    global EMA_MIN_BUFFER, ATR_MULTIPLIER, TRAIL_ATR_MULT, SL_ATR_MULT
    global RISK_PERCENT, DAILY_LOSS_LIMIT, DAILY_PROFIT_TARGET
    global MAX_TRADES_PER_DAY, MIN_SCORE

    if _initialized:
        return

    import MetaTrader5 as _mt5
    mt5 = _mt5

    import config as _config
    config = _config

    import shared_state as _shared_state
    shared_state = _shared_state

    from database.stats_db import (
        update_stats as _us, load_stats as _ls,
        check_daily_lock as _cdl, check_profit_lock as _cpl, log_trade as _lt,
    )
    update_stats = _us; load_stats = _ls
    check_daily_lock = _cdl; check_profit_lock = _cpl; log_trade = _lt

    from agent import calculate_score as _cs
    calculate_score = _cs
    from sessions import trading_session_open as _tso
    trading_session_open = _tso
    from filters import spread_ok as _sok
    spread_ok = _sok
    from utils.status_writer import write_status as _ws
    write_status = _ws
    from utils.logger import get_logger, get_trade_logger
    logger = get_logger(__name__)
    trade_log = get_trade_logger()
    from utils.mt5_connector import ensure_connected as _ec, connect_mt5 as _cmt5
    ensure_connected = _ec; connect_mt5 = _cmt5

    # Phase 2
    from indicators.rsi import calculate_rsi as _crsi
    calculate_rsi = _crsi
    from indicators.macd import calculate_macd as _cmacd
    calculate_macd = _cmacd
    from intelligence.regime import detect_regime as _dr, get_threshold as _gt, LABELS as _rl
    detect_regime = _dr; get_threshold = _gt; REGIME_LABELS = _rl
    from intelligence.news_filter import is_news_window as _inw
    is_news_window = _inw

    from paper.paper_trader import PaperTrader
    _paper_inst = PaperTrader() if config.PAPER_TRADING else None
    _paper = _paper_inst

    # Phase 4: RL agent
    from rl.agent import RLAgent
    _rl_agent_inst = RLAgent()

    # Assign to globals used by rest of module
    globals()['_paper'] = _paper_inst
    globals()['_rl_agent'] = _rl_agent_inst

    # ─── Constants ────────────────────────────────────────────
    SYMBOL       = config.SYMBOL
    M1_TF        = mt5.TIMEFRAME_M1
    H1_TF        = mt5.TIMEFRAME_H1
    H4_TF        = mt5.TIMEFRAME_H4
    EMA_PERIOD   = config.EMA_PERIOD
    ATR_PERIOD   = config.ATR_PERIOD
    SLEEP_TIME   = 0.2
    COOLDOWN_SECONDS    = config.COOLDOWN_SECONDS
    DEVIATION           = 20
    EMA_MIN_BUFFER      = 0.15
    ATR_MULTIPLIER      = 0.5
    TRAIL_ATR_MULT      = 1.2
    SL_ATR_MULT         = 1.5
    RISK_PERCENT        = config.RISK_PERCENT
    DAILY_LOSS_LIMIT    = config.DAILY_LOSS_LIMIT
    DAILY_PROFIT_TARGET = config.DAILY_PROFIT_TARGET
    MAX_TRADES_PER_DAY  = config.MAX_TRADES_PER_DAY
    MIN_SCORE           = config.MIN_SCORE_TO_TRADE

    # Write back to module globals so other functions see them
    g = globals()
    for name in ['SYMBOL', 'M1_TF', 'H1_TF', 'H4_TF', 'EMA_PERIOD', 'ATR_PERIOD',
                 'SLEEP_TIME', 'COOLDOWN_SECONDS', 'DEVIATION', 'EMA_MIN_BUFFER',
                 'ATR_MULTIPLIER', 'TRAIL_ATR_MULT', 'SL_ATR_MULT', 'RISK_PERCENT',
                 'DAILY_LOSS_LIMIT', 'DAILY_PROFIT_TARGET', 'MAX_TRADES_PER_DAY', 'MIN_SCORE']:
        g[name] = locals()[name]

    _initialized = True
    logger.info("Bot engine modules loaded (lazy init complete)")



# ─── Helpers ──────────────────────────────────────────────────

def _get_user_state(user_id: int) -> dict:
    """Helper to lazily fetch or initialize isolated state parameters per tenant user."""
    if user_id not in _user_states:
        _user_states[user_id] = {
            "state": STATE_WAITING,
            "trend": TREND_NONE,
            "pullback_seen": False,
            "last_trade_time": None,
            "last_known_profit": 0.0,
            "entry_price": 0.0,
            "sl": 0.0,
            "lot": 0.0,
            "score": 0,
            "entry_time": None,
            "ticket": None,
        }
    return _user_states[user_id]


def can_trade_again(user_id: int = 1) -> bool:
    ustate = _get_user_state(user_id)
    ltt = ustate["last_trade_time"]
    if ltt is None:
        return True
    return (time.time() - ltt) >= COOLDOWN_SECONDS


def get_positions():
    if config.PAPER_TRADING:
        return _paper.get_positions() or []
    return mt5.positions_get(symbol=SYMBOL) or []


def calculate_ema(values: list[float], period: int) -> float:
    k   = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def _get_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if 7 <= hour < 16:   return "LONDON"
    if 12 <= hour < 21:  return "NY"
    return "ASIAN"


def calculate_lot(atr: float, score: int, user_id: int = 1, risk_multiplier: float = 1.0) -> float:
    account = mt5.account_info()
    if account is None:
        return 0.01
    balance     = account.balance
    risk_amount = balance * (RISK_PERCENT / 100) * risk_multiplier
    sl_distance = atr * SL_ATR_MULT
    base_lot    = risk_amount / (sl_distance * 100)
    multiplier  = 1.50 if score >= 95 else 1.30 if score >= 85 else 1.00 if score >= 75 else 0.70
    stats = load_stats(user_id=user_id)
    if stats["loss_streak"] >= 3:   multiplier *= 0.60
    elif stats["loss_streak"] == 2: multiplier *= 0.80
    return round(max(base_lot * multiplier, 0.01), 2)


def send_order(user_id: int, risk_multiplier: float, order_type: int, atr: float, score: int, magic: int = 123456) -> bool:
    ustate = _get_user_state(user_id)

    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        logger.warning(f"send_order for user {user_id}: no tick data")
        return False

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    sl    = price - atr * SL_ATR_MULT if order_type == mt5.ORDER_TYPE_BUY else price + atr * SL_ATR_MULT
    lot   = calculate_lot(atr, score, user_id=user_id, risk_multiplier=risk_multiplier)
    side  = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"

    ustate["entry_price"] = price
    ustate["sl"]          = round(sl, 2)
    ustate["lot"]         = lot
    ustate["score"]       = score
    ustate["entry_time"]  = datetime.now().isoformat()

    user_name = f"User {user_id}"
    try:
        from database.db import _raw_conn
        with _raw_conn() as conn:
            row = conn.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                user_name = row["name"]
    except Exception:
        pass

    if config.PAPER_TRADING:
        ok = _paper.open_position(order_type, price, round(sl, 2), lot, score, SYMBOL, magic=magic)
        if ok:
            logger.info(f"📝 [PAPER] User {user_name} | {side} | {price:.2f} | SL={sl:.2f} | lot={lot} | score={score} | magic={magic}")
            paper_positions = _paper.get_positions()
            if paper_positions:
                ustate["ticket"] = paper_positions[-1].ticket
            if shared_state.send_message:
                shared_state.send_message(f"👤 {user_name} | 📝 [PAPER] {side}\nPrice:{price:.2f} SL:{sl:.2f} Lot:{lot}")
        return ok

    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
        "volume": lot, "type": order_type, "price": price,
        "sl": round(sl, 2), "deviation": DEVIATION,
        "comment": f"NUR SaaS {user_id}", "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "magic": magic,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order FAILED for user {user_id} retcode={result.retcode}")
        return False

    ustate["ticket"] = result.order
    trade_log.info(f"User {user_id} ({user_name}) | OPEN {side} price={price:.2f} sl={sl:.2f} lot={lot} score={score}")
    logger.info(f"📤 User {user_name} | {side} | {price:.2f} | SL={sl:.2f} | lot={lot} | score={score}")
    if shared_state.send_message:
        shared_state.send_message(f"👤 {user_name} | 📤 {side}\nPrice:{price:.2f} SL:{sl:.2f} Lot:{lot}")
    return True


def modify_sl(position, new_sl: float) -> None:
    if config.PAPER_TRADING:
        _paper.modify_sl(position.ticket, new_sl); return
    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                    "position": position.ticket, "sl": round(new_sl, 2)})


def trail_stop_loss(position, atr: float) -> None:
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None: return
    if position.type == mt5.ORDER_TYPE_BUY:
        new_sl = tick.bid - atr * TRAIL_ATR_MULT
        if position.sl == 0 or new_sl > position.sl:
            modify_sl(position, new_sl)
    elif position.type == mt5.ORDER_TYPE_SELL:
        new_sl = tick.ask + atr * TRAIL_ATR_MULT
        if position.sl == 0 or new_sl < position.sl:
            modify_sl(position, new_sl)


def _handle_trade_closed(pnl: float, exit_price: float, reason: str = "SL/TP", user_id: int = 1) -> None:
    ustate = _get_user_state(user_id)
    update_stats(pnl, user_id=user_id)
    log_trade(
        direction    = "BUY" if ustate["trend"] == TREND_BULLISH else "SELL",
        entry_price  = ustate["entry_price"],
        exit_price   = exit_price,
        sl           = ustate["sl"],
        lot          = ustate["lot"],
        score        = ustate["score"],
        pnl          = pnl,
        exit_reason  = reason,
        entry_time   = ustate["entry_time"] or "",
        exit_time    = datetime.now().isoformat(),
        is_paper     = config.PAPER_TRADING,
        session      = _get_session(),
        user_id      = user_id,
    )
    stats = load_stats(user_id=user_id)
    user_name = f"User {user_id}"
    try:
        from database.db import _raw_conn
        with _raw_conn() as conn:
            row = conn.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                user_name = row["name"]
    except Exception:
        pass

    logger.info(f"User {user_name} Closed PnL={pnl:+.2f} Today={stats['today_pnl']:.2f} W/L={stats['wins']}/{stats['losses']}")
    trade_log.info(f"User {user_id} ({user_name}) | CLOSE pnl={pnl:+.2f} exit={exit_price:.2f} [{reason}] regime={_current_regime}")
    if shared_state.send_message:
        emoji = "✅" if pnl > 0 else "❌"
        shared_state.send_message(
            f"👤 {user_name} | {emoji} Closed PnL:{pnl:+.2f}\nToday:{stats['today_pnl']:.2f} "
            f"W{stats['win_streak']}/L{stats['loss_streak']}"
        )
    ustate["last_known_profit"] = 0.0
    ustate["last_trade_time"]   = time.time()


def load_pending_commands(user_id: int) -> list[dict]:
    from database.db import _raw_conn
    conn = _raw_conn()
    try:
        rows = conn.execute("""
            SELECT id, command, direction, reason 
            FROM manual_commands 
            WHERE tenant_id = ? AND status = 'PENDING'
            ORDER BY created_at ASC
        """, (str(user_id),)).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error(f"Error loading manual commands for user {user_id}: {exc}")
        return []
    finally:
        conn.close()


def update_command_status(cmd_id: int, status: str) -> None:
    from database.db import get_connection
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE manual_commands 
                SET status = ?, executed_at = ? 
                WHERE id = ?
            """, (status, datetime.utcnow().isoformat(), cmd_id))
    except Exception as exc:
        logger.error(f"Error updating command status for command {cmd_id}: {exc}")


def close_position_mt5(position) -> bool:
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return False
    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": DEVIATION,
        "comment": "NUR Close Override",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE


def close_all_positions(user_id: int) -> int:
    closed_count = 0
    ustate = _get_user_state(user_id)
    
    if config.PAPER_TRADING and _paper:
        tick = mt5.symbol_info_tick(SYMBOL)
        price = tick.bid if tick else 2000.0
        user_ticket = ustate.get("ticket")
        if user_ticket is not None:
            pos = _paper.close_position(user_ticket, price, "CLOSE_ALL manual override")
            if pos:
                _handle_trade_closed(pos.profit, price, "Manual override close", user_id=user_id)
                closed_count += 1
        
        for pos in list(_paper.get_positions()):
            if getattr(pos, "magic", 0) == 999999:
                _paper.close_position(pos.ticket, price, "CLOSE_ALL manual override")
                closed_count += 1
    else:
        positions = mt5.positions_get(symbol=SYMBOL)
        if positions:
            for pos in positions:
                comment = getattr(pos, "comment", "")
                belongs = False
                if f"NUR SaaS {user_id}" in comment or comment == f"NUR SaaS {user_id}":
                    belongs = True
                elif user_id == 1 and not comment:
                    belongs = True
                
                if belongs:
                    if close_position_mt5(pos):
                        closed_count += 1
                        if ustate.get("ticket") == pos.ticket:
                            tick = mt5.symbol_info_tick(SYMBOL)
                            price = tick.bid if tick else pos.price_current
                            _handle_trade_closed(pos.profit, price, "Manual override close", user_id=user_id)
    
    ustate["state"] = STATE_COOLDOWN
    ustate["ticket"] = None
    return closed_count


def sync_agent_with_manual_trades(user_id: int) -> None:
    ustate = _get_user_state(user_id)
    positions = get_positions()
    
    user_position = None
    user_ticket = ustate.get("ticket")
    
    if user_ticket is not None:
        for pos in positions:
            if pos.ticket == user_ticket:
                user_position = pos
                break
                
    if not user_position:
        for pos in positions:
            magic = getattr(pos, "magic", 0)
            comment = getattr(pos, "comment", "")
            
            belongs = False
            if f"NUR SaaS {user_id}" in comment or comment == f"NUR SaaS {user_id}":
                belongs = True
            elif user_id == 1 and not comment:
                belongs = True
                
            if belongs and magic == 999999:
                user_position = pos
                break
                
    if user_position:
        if ustate["state"] != STATE_IN_TRADE:
            ustate["state"] = STATE_IN_TRADE
            ustate["ticket"] = user_position.ticket
            ustate["trend"] = TREND_BULLISH if user_position.type == mt5.ORDER_TYPE_BUY else TREND_BEARISH
            ustate["entry_price"] = user_position.price_open
            ustate["sl"] = user_position.sl
            ustate["lot"] = user_position.volume
            logger.info(f"Synchronized user {user_id} state to STATE_IN_TRADE with manual position ticket {user_position.ticket}")


def send_telegram_alert(message: str) -> None:
    logger.info(f"Telegram alert: {message}")
    if shared_state.send_message:
        try:
            shared_state.send_message(message)
        except Exception as exc:
            logger.error(f"Failed to send Telegram alert: {exc}")


# ─── Main loop ────────────────────────────────────────────────

def main() -> None:
    # Load all heavy modules NOW (in this background thread, not at app startup)
    _lazy_init()
    
    logger.info("Bot engine thread started — waiting for user authentication...")

    # ── Phase 1: DORMANT — wait until a user authenticates ────
    while not shared_state.shutdown:
        if shared_state.authenticated:
            break
        time.sleep(1)

    if shared_state.shutdown:
        logger.info("Shutdown received before authentication — exiting bot engine")
        return

    # ── Phase 2: CONNECT MT5 — only after authentication ──────
    if not connect_mt5():
        logger.error(f"MT5 init failed after auth: {mt5.last_error()}")
        # Don't crash the thread — just log and stay alive for retry
        while not shared_state.shutdown:
            if not shared_state.authenticated:
                logger.info("User de-authenticated — bot engine returning to dormant")
                break
            time.sleep(5)
            if connect_mt5():
                break
        else:
            return

    mode = "PAPER" if config.PAPER_TRADING else "LIVE"
    logger.info(f"MT5 connected | {mode} mode | symbol={SYMBOL}")

    # ── Phase 3: TRADING LOOP — runs while authenticated ──────
    while not shared_state.shutdown:
        # If user logs out, shut down MT5 and go back to dormant
        if not shared_state.authenticated:
            logger.info("User de-authenticated — shutting down MT5 and going dormant")
            try:
                mt5.shutdown()
            except Exception:
                pass
            # Re-enter dormant wait
            while not shared_state.shutdown:
                if shared_state.authenticated:
                    break
                time.sleep(1)
            if shared_state.shutdown:
                break
            # Re-connect MT5 after re-authentication
            if not connect_mt5():
                logger.error(f"MT5 reconnect failed: {mt5.last_error()}")
                continue
            logger.info("MT5 reconnected after re-authentication")
            continue

        if not ensure_connected():
            time.sleep(60); continue
        if not shared_state.bot_running:
            time.sleep(1); continue
        try:
            _tick()
        except Exception as exc:
            logger.error(f"Tick error: {exc}", exc_info=True)
            time.sleep(SLEEP_TIME * 5)

    # ── Phase 4: CLEAN SHUTDOWN ───────────────────────────────
    logger.info("Shutdown signal received — cleaning up MT5 connection")
    try:
        mt5.shutdown()
    except Exception:
        pass
    logger.info("Bot shutdown complete")


def _tick() -> None:
    global last_candle_time, _ema_history, _atr_history, _current_regime

    # ── Session filter ────────────────────────────────────────
    if not trading_session_open():
        time.sleep(30); return

    # ── News filter (Phase 2) ─────────────────────────────────
    blocked, event_name = is_news_window()
    if blocked:
        logger.info(f"📰 News blackout: {event_name} — skipping")
        time.sleep(60); return

    # ── Spread filter ─────────────────────────────────────────
    if not config.PAPER_TRADING and not spread_ok(SYMBOL):
        time.sleep(5); return

    # ── Fetch M1 + H1 + H4 data ──────────────────────────────
    m1_rates = mt5.copy_rates_from_pos(SYMBOL, M1_TF, 0, EMA_PERIOD + ATR_PERIOD + 40)
    h1_rates = mt5.copy_rates_from_pos(SYMBOL, H1_TF, 0, EMA_PERIOD + 3)
    h4_rates = mt5.copy_rates_from_pos(SYMBOL, H4_TF, 0, EMA_PERIOD + 3)

    if (m1_rates is None or len(m1_rates) < EMA_PERIOD + 3 or
            h1_rates is None or len(h1_rates) < EMA_PERIOD + 3):
        time.sleep(SLEEP_TIME); return

    last_closed = m1_rates[-2]
    if last_candle_time == last_closed["time"]:
        time.sleep(SLEEP_TIME); return
    last_candle_time = last_closed["time"]

    closes = [r["close"] for r in m1_rates]
    ema    = calculate_ema(closes[-EMA_PERIOD:], EMA_PERIOD)
    price  = last_closed["close"]

    # ATR
    atr_vals = [
        max(m1_rates[i]["high"] - m1_rates[i]["low"],
            abs(m1_rates[i]["high"] - m1_rates[i-1]["close"]),
            abs(m1_rates[i]["low"]  - m1_rates[i-1]["close"]))
        for i in range(-ATR_PERIOD, 0)
    ]
    atr = sum(atr_vals) / ATR_PERIOD

    # ── H1 trend ──────────────────────────────────────────────
    h1_closes = [r["close"] for r in h1_rates]
    h1_ema    = calculate_ema(h1_closes[-EMA_PERIOD:], EMA_PERIOD)
    h1_price  = h1_rates[-2]["close"]
    if   h1_price > h1_ema: h1_trend = TREND_BULLISH
    elif h1_price < h1_ema: h1_trend = TREND_BEARISH
    else:                   h1_trend = TREND_NONE

    # ── H4 bias (Phase 2) ─────────────────────────────────────
    h4_trend = TREND_NONE
    if h4_rates is not None and len(h4_rates) >= EMA_PERIOD + 3:
        h4_closes = [r["close"] for r in h4_rates]
        h4_ema    = calculate_ema(h4_closes[-EMA_PERIOD:], EMA_PERIOD)
        h4_price  = h4_rates[-2]["close"]
        if   h4_price > h4_ema: h4_trend = TREND_BULLISH
        elif h4_price < h4_ema: h4_trend = TREND_BEARISH

    # ── RSI + MACD (Phase 2) ──────────────────────────────────
    rsi              = calculate_rsi(closes, period=14)
    macd_l, macd_s, _ = calculate_macd(closes)

    # ── Regime detection (Phase 2) ────────────────────────────
    _ema_history.append(ema)
    _atr_history.append(atr)
    if len(_ema_history) > 50: _ema_history.pop(0)
    if len(_atr_history) > 50: _atr_history.pop(0)
    _current_regime = detect_regime(closes, _ema_history, atr, _atr_history)
    regime_score_threshold = get_threshold(_current_regime, MIN_SCORE)

    # Pull active SaaS traders dynamically from db
    from database.db import _raw_conn
    active_users = []
    try:
        with _raw_conn() as conn:
            rows = conn.execute("SELECT user_id, name, risk_multiplier FROM users WHERE is_active = 1").fetchall()
            active_users = [dict(r) for r in rows]
    except Exception as exc:
        logger.error(f"Failed to query active users: {exc}", exc_info=True)
        # Fallback to default user 1
        active_users = [{"user_id": 1, "name": "Default Tenant", "risk_multiplier": 1.0}]

    # ── Paper position update ─────────────────────────────────
    closed_paper_positions = []
    if config.PAPER_TRADING and _paper:
        closed_paper_positions = _paper.update(price)

    # Get active positions for trailing / state checks
    positions = get_positions()

    # ── RL Agent Manual Overrides State Synchronization ───────
    manual_trades = []
    for pos in positions:
        magic = getattr(pos, "magic", 0)
        if magic != 123456:
            pos_type = getattr(pos, "type", 0)
            manual_trades.append({
                'ticket': pos.ticket,
                'type': 'BUY' if pos_type == mt5.ORDER_TYPE_BUY else 'SELL',
                'entry_price': getattr(pos, "price_open", pos.price_open if hasattr(pos, "price_open") else 0.0),
                'current_price': getattr(pos, "price_current", pos.price_current if hasattr(pos, "price_current") else 0.0),
                'volume': getattr(pos, "volume", pos.volume if hasattr(pos, "volume") else 0.0),
                'pnl': getattr(pos, "profit", pos.profit if hasattr(pos, "profit") else 0.0),
                'magic': magic
            })
    
    if manual_trades:
        already_overridden = getattr(_rl_agent, "has_manual_override", False)
        agent_mode = _rl_agent.sync_with_manual_positions(manual_trades)
        if not already_overridden:
            logger.info(f"Agent synced. Mode: {agent_mode}")
            send_telegram_alert(
                f"⚠️ Agent Aware of Manual Trade\n"
                f"Direction: {manual_trades[0]['type']}\n"
                f"Entry: ${manual_trades[0]['entry_price']:.2f}\n"
                f"P&L: ${manual_trades[0]['pnl']:.2f}\n"
                f"Agent is now TRAILING this position."
            )
    else:
        _rl_agent.has_manual_override = False

    # ── Loop through active SaaS accounts dynamically ─────────
    for user in active_users:
        user_id = user["user_id"]
        risk_multiplier = user["risk_multiplier"]
        ustate = _get_user_state(user_id)

        # ── Check for pending manual commands ──────────────────
        pending_commands = load_pending_commands(user_id)
        if pending_commands:
            for cmd in pending_commands:
                cmd_id = cmd["id"]
                command = cmd["command"]
                direction = cmd.get("direction", "")
                reason = cmd.get("reason", "")
                
                try:
                    if command in ("BUY", "SELL"):
                        order_type = mt5.ORDER_TYPE_BUY if command == "BUY" else mt5.ORDER_TYPE_SELL
                        ok = send_order(user_id, risk_multiplier, order_type, atr, score=100, magic=999999)
                        if ok:
                            update_command_status(cmd_id, "EXECUTED")
                            try:
                                write_status(SYMBOL, ustate["state"], ema, trend=ustate["trend"], last_close=price if 'price' in locals() else None)
                            except Exception:
                                pass
                            send_telegram_alert(f"👤 {user['name']} | ✋ Manual {command} Executed\nReason: {reason}")
                        else:
                            update_command_status(cmd_id, "FAILED")
                    elif command == "CLOSE_ALL":
                        closed_count = close_all_positions(user_id)
                        update_command_status(cmd_id, "EXECUTED")
                        try:
                            write_status(SYMBOL, ustate["state"], ema, trend=ustate["trend"])
                        except Exception:
                            pass
                        send_telegram_alert(f"👤 {user['name']} | ✋ Manual CLOSE_ALL Executed\nClosed: {closed_count} positions")
                except Exception as exc:
                    logger.error(f"Failed to execute manual command {command} for user {user_id}: {exc}")
                    update_command_status(cmd_id, "FAILED")

        # ── Synchronize Agent State with Manual Override Trades ──
        sync_agent_with_manual_trades(user_id)

        # ── Check paper trade closure for this user ───────────
        if config.PAPER_TRADING and _paper:
            user_ticket = ustate.get("ticket")
            closed_pos = None
            for cp in closed_paper_positions:
                if cp.ticket == user_ticket:
                    closed_pos = cp
                    break
            if closed_pos:
                _handle_trade_closed(closed_pos.profit, price, "SL hit [paper]", user_id=user_id)
                ustate["state"] = STATE_COOLDOWN
                ustate["ticket"] = None

        # ── User-specific Daily Limits ────────────────────────
        stats = load_stats(user_id=user_id)
        if stats["today_trades"] >= MAX_TRADES_PER_DAY:
            continue
        if check_daily_lock(DAILY_LOSS_LIMIT, user_id=user_id):
            continue
        if check_profit_lock(DAILY_PROFIT_TARGET, user_id=user_id):
            continue

        # ── Live PnL check & Stop trailing for active user ────
        user_ticket = ustate.get("ticket")
        user_position = None
        if user_ticket is not None:
            for pos in positions:
                if pos.ticket == user_ticket:
                    user_position = pos
                    break

        live_pnl = user_position.profit if user_position else 0.0
        now_str = datetime.now().strftime("%H:%M")
        logger.info(
            f"{'[P]' if config.PAPER_TRADING else ''}{now_str} User {user['name']} | "
            f"price={price:.2f} ema={ema:.2f} | "
            f"h4={h4_trend} h1={h1_trend} rsi={rsi:.1f} | "
            f"state={ustate['state']} regime={REGIME_LABELS.get(_current_regime, _current_regime)} | "
            f"float={live_pnl:.2f}"
        )

        # ═══════════════════════════════════════════════════════
        # STATE MACHINE
        # ═══════════════════════════════════════════════════════

        if ustate["state"] == STATE_WAITING:
            if not can_trade_again(user_id):
                continue
            if abs(price - ema) < atr * ATR_MULTIPLIER:
                continue

            # ── Phase 4: RL agent veto/confirmation ────────────
            _pos_code = 0  # flat
            if user_position:
                _pos_code = 1 if user_position.type == mt5.ORDER_TYPE_BUY else 2
            _rl_state = {
                "rsi":              rsi,
                "macd_hist":        macd_l - macd_s,
                "ema_distance_pct": (price - ema) / max(ema, 1.0) * 100.0,
                "atr_normalized":   (atr - 1.5) / 1.0,  # rough normalization
                "hour":             datetime.now(timezone.utc).hour,
                "session":          0 if _get_session() == "ASIAN" else (1 if _get_session() == "LONDON" else 2),
                "position":         _pos_code,
            }
            try:
                rl_action = _rl_agent.predict(_rl_state)
                rl_conf   = _rl_agent.get_confidence(_rl_state)
            except Exception as exc:
                logger.warning(f"RL inference exception for user {user_id}: {exc} — falling back to HOLD", exc_info=True)
                rl_action = "HOLD"
                rl_conf   = {"HOLD": 0.333, "BUY": 0.333, "SELL": 0.333}
            logger.info(f"User {user_id} ({user['name']}) RL: {rl_action} | conf={rl_conf}")

            # RL veto: if agent says HOLD, skip this candle entirely
            if rl_action == "HOLD":
                continue

            # BUY — RL must agree with direction
            if h1_trend == TREND_BULLISH and rl_action == "BUY":
                if h4_trend == TREND_BEARISH:
                    continue

                if abs(price - ema) < EMA_MIN_BUFFER:
                    ustate["pullback_seen"] = True
                elif ustate["pullback_seen"] and price > ema:
                    score, reasons = calculate_score(
                        True, ustate["pullback_seen"], atr, price, ema, True,
                        rsi=rsi, macd_line=macd_l, macd_signal=macd_s, direction="BUY"
                    )
                    logger.info(f"User {user['name']} BUY score={score}/{regime_score_threshold} | {reasons}")
                    if score >= 60 and score >= regime_score_threshold:
                        if send_order(user_id, risk_multiplier, mt5.ORDER_TYPE_BUY, atr, score):
                            ustate["state"] = STATE_IN_TRADE
                            ustate["trend"] = TREND_BULLISH
                            ustate["pullback_seen"] = False

            # SELL — RL must agree with direction
            elif h1_trend == TREND_BEARISH and rl_action == "SELL":
                if h4_trend == TREND_BULLISH:
                    continue

                if abs(price - ema) < EMA_MIN_BUFFER:
                    ustate["pullback_seen"] = True
                elif ustate["pullback_seen"] and price < ema:
                    score, reasons = calculate_score(
                        True, ustate["pullback_seen"], atr, price, ema, True,
                        rsi=rsi, macd_line=macd_l, macd_signal=macd_s, direction="SELL"
                    )
                    logger.info(f"User {user['name']} SELL score={score}/{regime_score_threshold} | {reasons}")
                    if score >= 60 and score >= regime_score_threshold:
                        if send_order(user_id, risk_multiplier, mt5.ORDER_TYPE_SELL, atr, score):
                            ustate["state"] = STATE_IN_TRADE
                            ustate["trend"] = TREND_BEARISH
                            ustate["pullback_seen"] = False

        elif ustate["state"] == STATE_IN_TRADE:
            if not user_position:
                if not config.PAPER_TRADING:
                    _handle_trade_closed(ustate["last_known_profit"], price, "SL/TP", user_id=user_id)
                ustate["state"] = STATE_COOLDOWN
                ustate["ticket"] = None
            else:
                ustate["last_known_profit"] = user_position.profit
                trail_stop_loss(user_position, atr)

        elif ustate["state"] == STATE_COOLDOWN:
            if can_trade_again(user_id):
                ustate["state"] = STATE_WAITING

    # Write fallback engine status for user 1 (Default Tenant)
    try:
        u1 = _get_user_state(1)
        write_status(SYMBOL, u1["state"], ema, trend=u1["trend"], last_close=price)
    except Exception:
        pass

    time.sleep(SLEEP_TIME)


if __name__ == "__main__":
    main()
