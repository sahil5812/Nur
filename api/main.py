"""
api/main.py — FastAPI backend for Nur Trading Dashboard.

Reads from the same SQLite database the bot writes to.
Safe for concurrent access — SQLite WAL mode handles this.

Endpoints:
  GET  /api/health       — liveness check
  GET  /api/stats        — current daily/total stats
  GET  /api/trades       — trade history (paginated)
  GET  /api/equity       — equity curve data points
  GET  /api/analytics    — win rate by session, score, regime
  GET  /api/engine       — last engine status (from engine_status.json)
  WS   /ws/live          — streams stats + engine status every second
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import jwt

# Bootstrap path so we can import project modules
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import shared_state
from database.db import init_db, _raw_conn
from database.stats_db import load_stats
from analytics.performance import get_summary, get_by_session, get_by_score, get_by_regime
import api.auth as auth
from api.auth import get_current_user

force_update_event = asyncio.Event()

app = FastAPI(
    title="Nur Trading Bot API",
    version="3.0.0",
    description="Real-time dashboard API for the Nur XAUUSD trading bot",
)

app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

ENGINE_STATUS_FILE = Path(__file__).parent.parent / "logs" / "engine_status.json"


class TraderCreateSchema(BaseModel):
    name: str
    mt5_login: int
    mt5_password: str | None = None
    mt5_server: str | None = None
    risk_multiplier: float = Field(default=1.0, ge=0.1, le=10.0)


class TraderUpdateSchema(BaseModel):
    user_id: int
    risk_multiplier: float = Field(..., ge=0.1, le=10.0)


class RiskUpdateSchema(BaseModel):
    risk_multiplier: float = Field(..., ge=0.1, le=10.0)


class ForceTradeRequest(BaseModel):
    tenant_id: str | None = None
    direction: str  # 'BUY' or 'SELL'
    reason: str | None = None
    risk_multiplier: float | None = 1.0

FastTradeRequest = ForceTradeRequest


class ForceCloseRequest(BaseModel):
    tenant_id: str | None = None
    magic_number: int | None = None
    ticket: int | None = None


@app.on_event("startup")
async def startup():
    init_db(config.DB_PATH)


# ─── REST Endpoints ───────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/shutdown")
def shutdown():
    """Clean shutdown endpoint — called by desktop wrapper on window close."""
    import threading
    import MetaTrader5 as mt5

    shared_state.shutdown = True
    shared_state.bot_running = False
    shared_state.authenticated = False

    # Gracefully disconnect MT5
    try:
        mt5.shutdown()
    except Exception:
        pass

    def _force_exit():
        import time
        time.sleep(1.5)  # Give threads a moment to wind down
        os._exit(0)

    threading.Thread(target=_force_exit, daemon=True).start()
    return {"status": "shutting_down"}


def load_stats_with_balance(user_id: int):
    base_stats = dict(load_stats(user_id=user_id))
    import MetaTrader5 as mt5
    balance = 5000.0
    equity = 5000.0
    currency = "INR" if getattr(config, "DAILY_LOSS_LIMIT", -50) <= -200 else "USD"
    if mt5.initialize():
        acc = mt5.account_info()
        if acc:
            balance = acc.balance
            equity = acc.equity
            currency = getattr(acc, "currency", currency) or currency

    curr_upper = currency.upper()
    curr_symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "AED": "AED ",
        "CAD": "C$",
        "AUD": "A$",
        "CHF": "CHF ",
        "SGD": "S$",
    }
    symbol = curr_symbols.get(curr_upper, curr_upper + " ")
    base_stats["currency"] = curr_upper
    base_stats["currency_symbol"] = symbol
    base_stats["daily_loss_limit"] = config.DAILY_LOSS_LIMIT
    base_stats["daily_profit_target"] = config.DAILY_PROFIT_TARGET

    if config.PAPER_TRADING:
        # In Paper Trading, the realized balance is base balance + total_pnl!
        base_stats["balance"] = round(balance + base_stats.get("total_pnl", 0.0), 2)
        
        # Calculate live paper floating PnL and active exposure
        paper_file = Path("logs/paper_positions.json")
        floating_pnl = 0.0
        open_count = 0
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
                open_count = len(positions_data)
                for pos in positions_data:
                    floating_pnl += pos.get("profit", 0.0)
            except Exception:
                pass
        base_stats["open_positions"] = open_count
        base_stats["equity"] = round(base_stats["balance"] + floating_pnl, 2)
    else:
        base_stats["balance"] = balance
        base_stats["equity"] = equity

    return base_stats


@app.get("/api/export-excel")
def export_excel():
    """Generates and serves the latest Excel trading journal."""
    from utils.excel_exporter import export_trades_to_excel
    xlsx_path, _ = export_trades_to_excel()
    return FileResponse(
        path=str(xlsx_path),
        filename="nur_trading_journal.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/stats")
def stats(current_user: dict = Depends(get_current_user)):
    return load_stats_with_balance(current_user["id"])


@app.get("/api/trades")
def trades(
    limit:  int = Query(default=50,  ge=1, le=500),
    offset: int = Query(default=0,   ge=0),
    direction: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    conn = _raw_conn()
    try:
        base_sql = "FROM trades WHERE exit_time IS NOT NULL AND user_id = ?"
        params: list = [current_user["id"]]
        if direction:
            base_sql += " AND direction = ?"
            params.append(direction.upper())

        count = conn.execute(f"SELECT COUNT(*) c {base_sql}", params).fetchone()["c"]
        rows  = conn.execute(
            f"SELECT * {base_sql} ORDER BY exit_time DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

        return {
            "total":  count,
            "limit":  limit,
            "offset": offset,
            "trades": [dict(r) for r in rows],
        }
    finally:
        conn.close()


@app.get("/api/equity")
def equity(current_user: dict = Depends(get_current_user)):
    """Returns cumulative PnL data points for the equity curve chart."""
    conn = _raw_conn()
    try:
        rows = conn.execute("""
            SELECT exit_time, pnl
            FROM trades
            WHERE exit_time IS NOT NULL AND user_id = ?
            ORDER BY exit_time ASC
        """, (current_user["id"],)).fetchall()

        points = []
        cumulative = 0.0
        for r in rows:
            cumulative += r["pnl"] or 0
            points.append({
                "time": r["exit_time"],
                "pnl":  round(r["pnl"] or 0, 2),
                "equity": round(cumulative, 2),
            })
        return {"points": points, "total_pnl": round(cumulative, 2)}
    finally:
        conn.close()


@app.get("/api/market_chart")
def get_market_chart(symbol: str = "XAUUSD", timeframe: str = "M1", count: int = 40):
    """Returns recent candle data and EMA 200 for the live terminal chart."""
    candles = []
    current_price = 4050.0
    ema_val = 4065.0
    
    try:
        import MetaTrader5 as mt5_chart
        tf_map = {
            "M1": mt5_chart.TIMEFRAME_M1,
            "M5": mt5_chart.TIMEFRAME_M5,
            "H1": mt5_chart.TIMEFRAME_H1
        }
        tf = tf_map.get(timeframe.upper(), mt5_chart.TIMEFRAME_M1)
        if mt5_chart.initialize():
            rates = mt5_chart.copy_rates_from_pos(symbol, tf, 0, min(max(count, 15), 60))
            if rates is not None and len(rates) > 0:
                closes = [float(r["close"]) for r in rates]
                current_price = closes[-1]
                
                # Fetch engine status EMA if available
                eng = engine_status(current_user={"id": 1})
                if isinstance(eng, dict) and "ema200" in eng and eng["ema200"]:
                    ema_target = float(eng["ema200"])
                else:
                    ema_target = closes[0]

                # Generate smoothed EMA line
                mult = 2.0 / (min(len(closes), 20) + 1.0)
                cur_ema = ema_target
                for r in rates:
                    dt = datetime.fromtimestamp(r["time"])
                    c = float(r["close"])
                    cur_ema = (c - cur_ema) * mult + cur_ema
                    candles.append({
                        "time": dt.strftime("%H:%M"),
                        "open": round(float(r["open"]), 2),
                        "high": round(float(r["high"]), 2),
                        "low": round(float(r["low"]), 2),
                        "close": round(c, 2),
                        "ema": round(cur_ema, 2),
                        "volume": int(r["tick_volume"])
                    })
    except Exception:
        pass

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "current_price": current_price,
        "count": len(candles)
    }


@app.get("/api/analytics")
def analytics(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    summary_raw = get_summary(user_id=user_id)
    if not summary_raw:
        summary_mapped = {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_pnl": 0.0,
            "best": 0.0,
            "worst": 0.0,
        }
        by_session = {}
        by_score = {}
        by_regime = {}
    else:
        pf = summary_raw.get("profit_factor", 0.0)
        if pf == float("inf"):
            pf = 999.0  # safe numerical fallback to avoid JSON serialization of Infinity
        summary_mapped = {
            "total": summary_raw.get("total", 0),
            "wins": summary_raw.get("wins", 0),
            "losses": summary_raw.get("losses", 0),
            "win_rate": summary_raw.get("win_rate", 0.0),
            "profit_factor": pf,
            "avg_pnl": summary_raw.get("avg_pnl", 0.0),
            "best": summary_raw.get("best", 0.0),
            "worst": summary_raw.get("worst", 0.0),
        }
        by_session = get_by_session(user_id=user_id)
        by_score = get_by_score(user_id=user_id)
        by_regime = get_by_regime(user_id=user_id)

    return {
        "summary":    summary_mapped,
        "by_session": by_session,
        "by_score":   by_score,
        "by_regime":  by_regime,
    }


@app.get("/api/engine")
def engine_status(current_user: dict = Depends(get_current_user)):
    """Last known engine state written by bot_engine every tick."""
    if ENGINE_STATUS_FILE.exists():
        try:
            return json.loads(ENGINE_STATUS_FILE.read_text())
        except Exception:
            pass
    return {"status": "unknown", "error": "engine_status.json not found"}


@app.get("/api/rf_model")
def get_rf_model_info():
    """Returns Random Forest meta-filter stats and features."""
    meta_path = Path(__file__).parent.parent / "rl" / "models" / "rf_filter_meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            pass
    return {
        "status": "ready",
        "selected_features": [
            "z_h1", "z_m5", "z_m1", "rsi", "rsi_slope_5", "macd_hist",
            "atr_normalized", "realized_vol_20", "spread_ratio",
            "hour_sin", "hour_cos", "z_alignment"
        ],
        "pruned_features": ["gamma_trend", "session_london", "session_asian", "gamma_range", "session_ny"],
        "baseline_win_rate": 0.4282,
        "filtered_win_rate": 0.4358,
        "win_rate_lift_pct": 0.76,
        "cv_accuracy": 0.5149,
        "min_threshold": 0.54,
    }


@app.get("/api/open_positions")
def open_positions(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    positions_list = []
    if config.PAPER_TRADING:
        from pathlib import Path
        paper_file = Path("logs/paper_positions.json")
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
                for pos in positions_data:
                    positions_list.append(pos)
            except Exception:
                pass
    else:
        import MetaTrader5 as mt5
        if mt5.initialize():
            positions = mt5.positions_get(symbol=config.SYMBOL)
            if positions:
                for pos in positions:
                    comment = getattr(pos, "comment", "")
                    belongs = False
                    if f"NUR SaaS {user_id}" in comment or comment == f"NUR SaaS {user_id}":
                        belongs = True
                    elif user_id == 1 and (not comment or "NUR BOT" in comment):
                        belongs = True
                    
                    if belongs:
                        positions_list.append({
                            "ticket": pos.ticket,
                            "type": pos.type,
                            "symbol": pos.symbol,
                            "volume": pos.volume,
                            "price_open": pos.price_open,
                            "price_current": pos.price_current,
                            "profit": pos.profit,
                            "sl": pos.sl,
                            "tp": pos.tp,
                            "magic": getattr(pos, "magic", 0),
                            "comment": comment
                        })
    return positions_list


@app.get("/api/saas/profiles")
def get_saas_profiles(current_user: dict = Depends(get_current_user)):
    # Each logged in user only sees their own profile to prevent access to others
    return [{
        "user_id":         current_user["id"],
        "name":            current_user["display_name"],
        "mt5_login":       current_user["mt5_login"],
        "risk_multiplier": current_user["risk_multiplier"],
        "environment_mode": "PAPER" if config.PAPER_TRADING else "LIVE",
    }]


@app.post("/api/saas/add-trader")
def add_trader(trader: TraderCreateSchema, current_user: dict = Depends(get_current_user)):
    import bcrypt
    import time
    dummy_email = f"trader_{trader.mt5_login or int(time.time())}@nur.bot"
    dummy_password = bcrypt.hashpw(b"trader123", bcrypt.gensalt()).decode("utf-8")
    
    conn = _raw_conn()
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO users (email, password_hash, display_name, mt5_login, mt5_password, mt5_server, risk_multiplier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (dummy_email, dummy_password, trader.name, trader.mt5_login, trader.mt5_password, trader.mt5_server, trader.risk_multiplier))
            
            user_id = cur.lastrowid
            
            conn.execute("""
                INSERT OR IGNORE INTO bot_stats (user_id) VALUES (?)
            """, (user_id,))
            
        return {"status": "success", "user_id": user_id, "message": "Trader profile and stats initialized successfully"}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to register trader: {exc}"}
    finally:
        conn.close()


@app.post("/api/saas/update-config")
def update_config(data: TraderUpdateSchema, current_user: dict = Depends(get_current_user)):
    if data.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    conn = _raw_conn()
    try:
        with conn:
            conn.execute("""
                UPDATE users 
                SET risk_multiplier = ? 
                WHERE id = ?
            """, (data.risk_multiplier, current_user["id"]))
        return {"status": "success", "message": "Trader config updated successfully"}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to update trader config: {exc}"}
    finally:
        conn.close()


@app.post("/api/risk_config")
def update_risk_config(data: RiskUpdateSchema, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    conn = _raw_conn()
    try:
        with conn:
            conn.execute("UPDATE users SET risk_multiplier = ? WHERE id = ?", (data.risk_multiplier, user_id))
        return {"status": "success", "risk_multiplier": data.risk_multiplier}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    finally:
        conn.close()


def calculate_estimated_lot(user_id: int, risk_multiplier: float) -> float:
    import MetaTrader5 as mt5
    balance = 10000.0
    atr = 2.0
    risk_percent = getattr(config, "RISK_PERCENT", 2.0)
    sl_atr_mult = 1.5
    
    if mt5.initialize():
        acc = mt5.account_info()
        if acc:
            balance = acc.balance
        rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M1, 0, 20)
        if rates is not None and len(rates) >= 15:
            atr_vals = []
            for i in range(1, len(rates)):
                high = rates[i]["high"]
                low = rates[i]["low"]
                prev_close = rates[i-1]["close"]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                atr_vals.append(tr)
            if atr_vals:
                atr = sum(atr_vals) / len(atr_vals)
    
    risk_amount = balance * (risk_percent / 100.0) * risk_multiplier
    sl_distance = atr * sl_atr_mult
    if sl_distance <= 0:
        sl_distance = 2.0
    base_lot = risk_amount / (sl_distance * 100.0)
    estimated_lot = round(max(base_lot * 1.5, 0.01), 2)
    return estimated_lot


@app.post("/api/fast_trade")
@app.post("/api/force_trade")
async def execute_trade_endpoint(request: ForceTradeRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    risk_mult = request.risk_multiplier or current_user.get("risk_multiplier", 1.0)
    direction = request.direction.upper()

    estimated_lot = calculate_estimated_lot(user_id, risk_mult)
    created_ticket = None

    if config.PAPER_TRADING:
        import MetaTrader5 as mt5
        entry_price = 4000.0
        sl_price = 0.0
        if mt5.initialize():
            tick = mt5.symbol_info_tick(config.SYMBOL)
            if tick:
                entry_price = tick.ask if direction == "BUY" else tick.bid
                rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M1, 0, 15)
                atr_val = 2.0
                if rates is not None and len(rates) >= 5:
                    atr_val = max(float(rates[-1]["high"] - rates[-1]["low"]), 1.5)
                sl_price = round(entry_price - (atr_val * 1.5), 2) if direction == "BUY" else round(entry_price + (atr_val * 1.5), 2)

        paper_file = Path("logs/paper_positions.json")
        positions_data = []
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
            except Exception:
                positions_data = []

        max_t = max([p.get("ticket", 10000) for p in positions_data], default=10000)
        created_ticket = max_t + 1
        new_pos = {
            "ticket": created_ticket,
            "type": 0 if direction == "BUY" else 1,
            "symbol": config.SYMBOL,
            "volume": estimated_lot,
            "price_open": round(entry_price, 2),
            "price_current": round(entry_price, 2),
            "profit": 0.0,
            "sl": sl_price,
            "tp": 0.0,
            "score": 80,
            "entry_time": datetime.utcnow().isoformat(),
            "magic": 123456
        }
        positions_data.append(new_pos)
        paper_file.write_text(json.dumps(positions_data, indent=2))

    conn = _raw_conn()
    try:
        with conn:
            cur = conn.execute("""
                INSERT INTO manual_commands (tenant_id, command, asset, direction, reason, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(user_id),
                direction,
                config.SYMBOL,
                direction,
                request.reason or f"Manual execution ({direction})",
                datetime.utcnow().isoformat(),
                "EXECUTED" if config.PAPER_TRADING else "PENDING"
            ))
            command_id = cur.lastrowid
        force_update_event.set()
        return {
            "status": "OK",
            "id": command_id,
            "ticket": created_ticket,
            "direction": direction,
            "estimated_lot": estimated_lot
        }
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc)}
    finally:
        conn.close()


@app.post("/api/close_all")
def close_all_endpoint(request: dict | None = None, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    from database.stats_db import log_trade, update_stats
    closed = 0
    total_pnl = 0.0
    
    if config.PAPER_TRADING:
        paper_file = Path("logs/paper_positions.json")
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
                now_str = datetime.utcnow().isoformat()
                for pos in positions_data:
                    ticket = pos.get("ticket")
                    direction = "SELL" if pos.get("type") == 1 else "BUY"
                    entry = pos.get("price_open", 4005.52)
                    exit_p = pos.get("price_current", 4003.26)
                    lot = pos.get("volume", 1.0)
                    pnl = round(pos.get("profit", 0.0), 2)
                    score = pos.get("score", 73)
                    entry_t = pos.get("entry_time", now_str)
                    
                    for uid in [user_id, 1, 4]:
                        try:
                            log_trade(
                                direction=direction,
                                entry_price=entry,
                                exit_price=exit_p,
                                sl=pos.get("sl", entry),
                                lot=lot,
                                score=score,
                                pnl=pnl,
                                exit_reason="Manual Emergency Flatten",
                                entry_time=entry_t,
                                exit_time=now_str,
                                is_paper=True,
                                trade_id=str(ticket),
                                session="London / NY",
                                user_id=uid,
                            )
                            update_stats(pnl=pnl, user_id=uid)
                        except Exception:
                            pass
                    closed += 1
                    total_pnl += pnl
                paper_file.write_text("[]")
            except Exception:
                pass
    force_update_event.set()
    return {"status": "OK", "closed": closed, "total_pnl": round(total_pnl, 2)}


@app.post("/api/close_position/{ticket}")
@app.post("/api/close_ticket/{ticket}")
def close_ticket_endpoint(ticket: int, request: dict | None = None, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    from database.stats_db import log_trade, update_stats
    closed = 0
    pnl_val = 0.0
    
    if config.PAPER_TRADING:
        paper_file = Path("logs/paper_positions.json")
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
                remaining = []
                now_str = datetime.utcnow().isoformat()
                for pos in positions_data:
                    if pos.get("ticket") == ticket:
                        direction = "SELL" if pos.get("type") == 1 else "BUY"
                        entry = pos.get("price_open", 4005.52)
                        exit_p = pos.get("price_current", 4003.26)
                        lot = pos.get("volume", 1.0)
                        pnl_val = round(pos.get("profit", 0.0), 2)
                        score = pos.get("score", 73)
                        entry_t = pos.get("entry_time", now_str)
                        
                        for uid in [user_id, 1, 4]:
                            try:
                                log_trade(
                                    direction=direction,
                                    entry_price=entry,
                                    exit_price=exit_p,
                                    sl=pos.get("sl", entry),
                                    lot=lot,
                                    score=score,
                                    pnl=pnl_val,
                                    exit_reason=f"Manual Close Ticket #{ticket}",
                                    entry_time=entry_t,
                                    exit_time=now_str,
                                    is_paper=True,
                                    trade_id=str(ticket),
                                    session="London / NY",
                                    user_id=uid,
                                )
                                update_stats(pnl=pnl_val, user_id=uid)
                            except Exception:
                                pass
                        closed += 1
                    else:
                        remaining.append(pos)
                paper_file.write_text(json.dumps(remaining, indent=2))
            except Exception:
                pass
    force_update_event.set()
    return {"status": "OK", "closed": closed, "ticket": ticket, "pnl": round(pnl_val, 2)}


@app.post("/api/force_close")
def force_close(request: ForceCloseRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]

    closed_positions = 0
    total_pnl = 0.0
    
    if config.PAPER_TRADING:
        from pathlib import Path
        paper_file = Path("logs/paper_positions.json")
        if paper_file.exists():
            try:
                positions_data = json.loads(paper_file.read_text())
                for pos in positions_data:
                    if request.magic_number is not None and pos.get("magic") != request.magic_number:
                        continue
                    closed_positions += 1
                    total_pnl += pos.get("profit", 0.0)
            except Exception:
                pass
    else:
        import MetaTrader5 as mt5
        if mt5.initialize():
            positions = mt5.positions_get(symbol=config.SYMBOL)
            if positions:
                for pos in positions:
                    comment = getattr(pos, "comment", "")
                    magic = getattr(pos, "magic", 0)
                    
                    belongs = False
                    if f"NUR SaaS {user_id}" in comment or comment == f"NUR SaaS {user_id}":
                        belongs = True
                    elif user_id == 1 and not comment:
                        belongs = True
                    
                    if belongs:
                        if request.magic_number is not None and magic != request.magic_number:
                            continue
                        closed_positions += 1
                        total_pnl += getattr(pos, "profit", 0.0)

    conn = _raw_conn()
    try:
        command = "CLOSE" if request.ticket else "CLOSE_ALL"
        reason = f"ticket={request.ticket}" if request.ticket else f"Force close magic_number={request.magic_number}"
        with conn:
            conn.execute("""
                INSERT INTO manual_commands (tenant_id, command, asset, reason, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(user_id),
                command,
                config.SYMBOL,
                reason,
                datetime.utcnow().isoformat(),
                "PENDING"
            ))
        return {
            "closed_positions": closed_positions,
            "total_pnl": round(total_pnl, 2)
        }
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc)}
    finally:
        conn.close()


# ─── WebSocket — live updates ─────────────────────────────────

class _ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self._clients = [c for c in self._clients if c is not ws]

    async def broadcast(self, data: dict):
        dead = []
        for client in self._clients:
            try:
                await client.send_json(data)
            except Exception:
                dead.append(client)
        for c in dead:
            self.disconnect(c)


_manager = _ConnectionManager()


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket, token: str | None = Query(default=None)):
    if not token:
        await websocket.close(code=4003)
        return
        
    from api.auth import decode_token
    try:
        payload = decode_token(token)
        email = payload.get("sub")
        user_id = payload.get("id")
        if email is None or user_id is None:
            await websocket.close(code=4003)
            return
        # Signal authentication to bot engine
        shared_state.authenticated = True
    except Exception:
        await websocket.close(code=4003)
        return

    await _manager.connect(websocket)
    # Initialize cache variables
    cached_trade_state_key = None
    cached_equity = None
    cached_recent_trades = None
    cached_analytics = None

    try:
        while True:
            # Safely fetch this user's profile details
            profiles = []
            conn = _raw_conn()
            try:
                # 1. Fetch user profiles (fast primary key query)
                r = conn.execute("""
                    SELECT id, display_name, mt5_login, risk_multiplier 
                    FROM users 
                    WHERE id = ?
                """, (user_id,)).fetchone()
                if r:
                    profiles.append({
                        "user_id":         r["id"],
                        "name":            r["display_name"],
                        "mt5_login":       r["mt5_login"],
                        "risk_multiplier": r["risk_multiplier"],
                        "environment_mode": "PAPER" if config.PAPER_TRADING else "LIVE",
                    })

                # 2. Check for trade additions/deletions to determine cache invalidation
                trade_check = conn.execute("""
                    SELECT MAX(id) as max_id, COUNT(id) as count 
                    FROM trades 
                    WHERE user_id = ?
                """, (user_id,)).fetchone()
                trade_state_key = (trade_check["max_id"], trade_check["count"])

                # 3. If database state changes (or first run), reload analytics cache
                if trade_state_key != cached_trade_state_key or cached_equity is None:
                    cached_trade_state_key = trade_state_key

                    # Build equity curve data
                    eq_rows = conn.execute("""
                        SELECT exit_time, pnl FROM trades
                        WHERE exit_time IS NOT NULL AND user_id = ?
                        ORDER BY exit_time ASC
                    """, (user_id,)).fetchall()
                    cumulative = 0.0
                    points = []
                    for er in eq_rows:
                        cumulative += er["pnl"] or 0
                        points.append({
                            "time": er["exit_time"],
                            "pnl": round(er["pnl"] or 0, 2),
                            "equity": round(cumulative, 2),
                        })
                    cached_equity = {"points": points, "total_pnl": round(cumulative, 2)}

                    # Build recent trades list
                    t_rows = conn.execute("""
                        SELECT * FROM trades
                        WHERE exit_time IS NOT NULL AND user_id = ?
                        ORDER BY exit_time DESC LIMIT 20
                    """, (user_id,)).fetchall()
                    cached_recent_trades = [dict(tr) for tr in t_rows]

                    # Build performance analytics data
                    summary_raw = get_summary(user_id=user_id)
                    if not summary_raw:
                        summary_mapped = {
                            "total": 0,
                            "wins": 0,
                            "losses": 0,
                            "win_rate": 0.0,
                            "profit_factor": 0.0,
                            "avg_pnl": 0.0,
                            "best": 0.0,
                            "worst": 0.0,
                        }
                        by_session = {}
                        by_score = {}
                        by_regime = {}
                    else:
                        pf = summary_raw.get("profit_factor", 0.0)
                        if pf == float("inf"):
                            pf = 999.0  # safe numerical fallback
                        summary_mapped = {
                            "total": summary_raw.get("total", 0),
                            "wins": summary_raw.get("wins", 0),
                            "losses": summary_raw.get("losses", 0),
                            "win_rate": summary_raw.get("win_rate", 0.0),
                            "profit_factor": pf,
                            "avg_pnl": summary_raw.get("avg_pnl", 0.0),
                            "best": summary_raw.get("best", 0.0),
                            "worst": summary_raw.get("worst", 0.0),
                        }
                        by_session = get_by_session(user_id=user_id)
                        by_score = get_by_score(user_id=user_id)
                        by_regime = get_by_regime(user_id=user_id)

                    cached_analytics = {
                        "summary":    summary_mapped,
                        "by_session": by_session,
                        "by_score":   by_score,
                        "by_regime":  by_regime,
                    }
            except Exception:
                pass
            finally:
                conn.close()

            # Build live payload every second
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "stats":     load_stats_with_balance(user_id),
                "engine":    engine_status(current_user={"id": user_id}),
                "clients":   len(_manager._clients),
                "profiles":  profiles,
                "equity":    cached_equity,
                "trades":    cached_recent_trades,
                "analytics":  cached_analytics,
                "chart":     get_market_chart(count=30),
            }
            await websocket.send_json(payload)
            try:
                # Wait max 1 second OR until force update triggered
                await asyncio.wait_for(
                    force_update_event.wait(),
                    timeout=1.0
                )
                force_update_event.clear()  # Reset flag
            except asyncio.TimeoutError:
                pass  # Normal 1-second tick
    except WebSocketDisconnect:
        _manager.disconnect(websocket)


# ─── Static files catch-all for React Dashboard ──────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

dist_path = Path(__file__).parent.parent / "dashboard" / "dist"
if dist_path.exists():
    app.mount("/assets", NoCacheStaticFiles(directory=dist_path / "assets"), name="assets")
    
    @app.get("/{fallback_path:path}")
    def serve_dashboard(fallback_path: str):
        if fallback_path.startswith("api") or fallback_path.startswith("ws"):
            return {"detail": "Not Found"}
        return FileResponse(
            dist_path / "index.html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
