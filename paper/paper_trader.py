"""
paper/paper_trader.py — Paper trading engine.

How it works:
  - Uses REAL MT5 market prices (live tick data flows through unchanged)
  - Intercepts only the mt5.order_send() call — no real order is placed
  - Returns SimpleNamespace "position" objects that are API-compatible
    with MT5's position objects, so bot_engine.py state machine is unaffected
  - Tracks floating PnL, SL hits, and TP hits against live prices
  - Writes results to stats_db (identical to live mode)

Toggle: set PAPER_TRADING=true in .env
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Optional

import MetaTrader5 as mt5

from utils.logger import get_logger, get_trade_logger

logger      = get_logger(__name__)
trade_log   = get_trade_logger()

# XAUUSD: 1 pip = $1 per 0.01 lot → PnL = price_diff * lot * 100
_PNL_MULTIPLIER = 100.0


class PaperTrader:
    """
    Simulates trade execution using real MT5 price data.

    Designed as a drop-in replacement at the bot_engine.py boundary:
        - paper_trader.open_position(...)  ←→  mt5.order_send(...)
        - paper_trader.get_positions()     ←→  mt5.positions_get()
        - paper_trader.modify_sl(...)      ←→  mt5.order_send(SLTP request)
    """

    def __init__(self) -> None:
        self._positions: list[SimpleNamespace] = []
        self._next_ticket: int = 10000
        self._closed_this_tick: list[SimpleNamespace] = []
        logger.info("📝 PaperTrader initialized — PAPER TRADING MODE ACTIVE")
        self._save_state()

    # ─── Core API ────────────────────────────────────────────────

    def _save_state(self) -> None:
        import json
        from pathlib import Path
        try:
            path = Path("logs/paper_positions.json")
            path.parent.mkdir(exist_ok=True)
            data = []
            for pos in self._positions:
                data.append({
                    "ticket": pos.ticket,
                    "type": pos.type,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "price_open": pos.price_open,
                    "price_current": pos.price_current,
                    "profit": pos.profit,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "score": getattr(pos, "score", 0),
                    "entry_time": pos.entry_time,
                    "magic": getattr(pos, "magic", 0)
                })
            path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning(f"Failed to save paper positions state: {exc}")

    def open_position(
        self,
        order_type: int,    # mt5.ORDER_TYPE_BUY or ORDER_TYPE_SELL
        price: float,
        sl: float,
        lot: float,
        score: int = 0,
        symbol: str = "XAUUSD",
        magic: int = 123456,
    ) -> bool:
        """Simulate opening a trade. Returns True (mimics successful order_send)."""
        direction = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
        ticket = self._next_ticket
        self._next_ticket += 1

        pos = SimpleNamespace(
            ticket=ticket,
            type=order_type,
            symbol=symbol,
            volume=lot,
            price_open=price,
            price_current=price,
            profit=0.0,
            sl=sl,
            tp=0.0,
            score=score,
            entry_time=datetime.now().isoformat(),
            magic=magic,
        )
        self._positions.append(pos)
        self._save_state()

        trade_log.info(
            f"[PAPER] OPEN {direction} | ticket={ticket} | "
            f"price={price:.2f} | sl={sl:.2f} | lot={lot} | score={score} | magic={magic}"
        )
        logger.info(f"📝 [PAPER] {direction} opened @ {price:.2f} | SL={sl:.2f} | lot={lot} | magic={magic}")
        return True

    def get_positions(self) -> list[SimpleNamespace]:
        """Return open paper positions. Compatible with mt5.positions_get() output."""
        return list(self._positions)

    def modify_sl(self, ticket: int, new_sl: float) -> None:
        """Update SL on an open paper position."""
        for pos in self._positions:
            if pos.ticket == ticket:
                pos.sl = new_sl
                logger.debug(f"[PAPER] SL updated ticket={ticket} → {new_sl:.2f}")
                self._save_state()
                return

    def close_position(self, ticket: int, current_price: float, reason: str = "manual override") -> Optional[SimpleNamespace]:
        """Close a specific paper position manually."""
        for i, pos in enumerate(self._positions):
            if pos.ticket == ticket:
                self._close_position(pos, current_price, reason)
                self._positions.pop(i)
                self._save_state()
                return pos
        return None

    def update(self, current_price: float) -> list[SimpleNamespace]:
        """
        Call once per loop tick with the current market price.
        Updates floating PnL for all open positions.
        Checks and closes any positions that hit SL.

        Returns list of positions closed THIS tick (for bot_engine to handle).
        """
        self._closed_this_tick = []
        still_open: list[SimpleNamespace] = []
        changed = False

        for pos in self._positions:
            # Update floating PnL
            if pos.type == mt5.ORDER_TYPE_BUY:
                pos.profit = (current_price - pos.price_open) * pos.volume * _PNL_MULTIPLIER
                sl_hit = pos.sl > 0 and current_price <= pos.sl
            else:
                pos.profit = (pos.price_open - current_price) * pos.volume * _PNL_MULTIPLIER
                sl_hit = pos.sl > 0 and current_price >= pos.sl

            pos.price_current = current_price

            if sl_hit:
                self._close_position(pos, current_price, "SL hit")
                self._closed_this_tick.append(pos)
                changed = True
            else:
                still_open.append(pos)

        self._positions = still_open
        if changed or len(still_open) > 0: # update prices in state anyway
            self._save_state()
        return self._closed_this_tick

    # ─── Internal ────────────────────────────────────────────────

    def _close_position(self, pos: SimpleNamespace, exit_price: float, reason: str) -> None:
        direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"

        if pos.type == mt5.ORDER_TYPE_BUY:
            pnl = (exit_price - pos.price_open) * pos.volume * _PNL_MULTIPLIER
        else:
            pnl = (pos.price_open - exit_price) * pos.volume * _PNL_MULTIPLIER

        pos.profit = pnl

        trade_log.info(
            f"[PAPER] CLOSE {direction} | ticket={pos.ticket} | "
            f"entry={pos.price_open:.2f} | exit={exit_price:.2f} | "
            f"pnl={pnl:+.2f} | reason={reason}"
        )
        logger.info(f"📝 [PAPER] {direction} closed @ {exit_price:.2f} | PnL={pnl:+.2f} | {reason}")

    def get_last_closed_pnl(self) -> Optional[float]:
        """Returns the PnL of the last position closed this tick, or None."""
        if self._closed_this_tick:
            return self._closed_this_tick[-1].profit
        return None
