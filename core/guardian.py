"""
core/guardian.py — Hard circuit breaker for live trading risk limits.

The guardian is checked every engine loop and can flatten the book when
a hard limit trips.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5

from core.models import RiskConfig
from data.storage import Storage
from utils.logger import logger
import shared_state


@dataclass
class GuardianResult:
    tripped: bool
    reason: str = ""
    detail: str = ""


class RiskGuardian:
    """
    Monitors hard risk limits and closes open positions when any limit trips.

    Checks:
    - Daily max loss exceeded
    - Total/equity max drawdown exceeded
    - Margin level below threshold
    - Abnormal spread / slippage
    """

    def __init__(self, config: RiskConfig, storage: Storage, broker, symbol: str):
        self.config = config
        self.storage = storage
        self.broker = broker
        self.symbol = symbol

    def check(self) -> GuardianResult:
        """Return the first tripped hard-limit check, or a non-tripped result."""
        checks = [
            self._check_daily_loss,
            self._check_drawdown,
            self._check_margin,
            self._check_spread_slippage,
        ]
        for check in checks:
            result = check()
            if result.tripped:
                return result
        return GuardianResult(tripped=False)

    def check_and_apply(self) -> GuardianResult:
        """Run checks and apply panic close / shared-state updates if tripped."""
        result = self.check()
        if not result.tripped:
            return result

        logger.error(f"🚨 RiskGuardian trip: {result.reason} ({result.detail})")
        closed_count = self.broker.panic_close_all(self.symbol)
        shared_state.hard_stop = True
        shared_state.panic_mode = True

        if shared_state.send_message:
            shared_state.send_message(
                "🚨 *RiskGuardian Trip*\n"
                f"▪️ *Reason:* {result.reason}\n"
                f"▪️ *Detail:* {result.detail}\n"
                f"▪️ *Closed Positions:* {closed_count}"
            )
        return result

    def _check_daily_loss(self) -> GuardianResult:
        report = self.storage.get_report_data()
        today_profit = float(report.get("today_profit", 0.0))
        limit = float(self.config.panic_daily_loss_limit)
        if today_profit <= -limit:
            return GuardianResult(
                tripped=True,
                reason="Daily max loss exceeded",
                detail=f"today_profit={today_profit:.2f}, limit=-{limit:.2f}",
            )
        return GuardianResult(tripped=False)

    def _check_drawdown(self) -> GuardianResult:
        stats = self.storage.get_aggregated_stats()
        drawdown = float(stats.get("max_drawdown", 0.0))
        limit = float(self.config.panic_drawdown_limit)
        if drawdown >= limit:
            return GuardianResult(
                tripped=True,
                reason="Total/equity max drawdown exceeded",
                detail=f"max_drawdown={drawdown:.2f}, limit={limit:.2f}",
            )
        return GuardianResult(tripped=False)

    def _check_margin(self) -> GuardianResult:
        account = mt5.account_info()
        if account is None:
            return GuardianResult(
                tripped=True,
                reason="Margin check failed",
                detail="MT5 account_info returned None",
            )

        free_margin = float(account.free_margin)
        margin_required = float(account.margin)
        threshold = margin_required * float(self.config.panic_margin_multiplier)

        if free_margin < threshold:
            return GuardianResult(
                tripped=True,
                reason="Margin level below threshold",
                detail=f"free_margin={free_margin:.2f}, required_threshold={threshold:.2f}",
            )
        return GuardianResult(tripped=False)

    def _check_spread_slippage(self) -> GuardianResult:
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return GuardianResult(tripped=False)

        spread = abs(float(tick.ask) - float(tick.bid))
        mid = (float(tick.ask) + float(tick.bid)) / 2.0
        if mid <= 0:
            return GuardianResult(tripped=False)

        threshold = mid * float(self.config.panic_spread_threshold)
        if spread >= threshold:
            return GuardianResult(
                tripped=True,
                reason="Abnormal spread",
                detail=f"spread={spread:.5f}, threshold={threshold:.5f}",
            )
        return GuardianResult(tripped=False)
