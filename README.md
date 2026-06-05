# Nur Trading Agent

Production-grade, event-driven MT5 algorithmic trading engine featuring multi-timeframe confirmation (H1 ∩ M5 ∩ M1), SQLite database persistence, advanced risk controls, and a Telegram Command Center.

## Quick commands

| Goal | Command |
|------|---------|
| Live trading (MT5) | `python main.py` or `run_live.bat` |
| Backtest | `python backtest/engine_fixed.py` or `run_backtest.bat` |

## Updated Layout

- `/core` — Core trading engine logic:
  - `engine.py` — Main execution and orchestration loop.
  - `strategy.py` — MTF signal logic (H1 direction, M5 structure confirmation, M1 entry trigger).
  - `risk.py` — Timezone-aware sessions (London/NY), lot calculation, margin, and drawdown stops.
  - `state.py` — State machine (WAITING ➔ IN_TRADE ➔ COOLDOWN).
  - `models.py` — Pydantic models for validated ticks, bars, and settings.
- `/data` — Persistence and retrieval:
  - `storage.py` — SQLite trade logging and dynamic portfolio analytics.
  - `data_provider.py` — Market data provider with a TTL cache to minimize API strain.
- `/integrations` — Integrations:
  - `telegram_bot.py` — Async Telegram command handler (/start, /status, /report, /panic).
- `/utils` — Utilities:
  - `logger.py` — Thread-safe logs saved to `logs/trading.log`.
  - `helpers.py` — Formatting, time duration, and timezone checking functions.
- `shared_state.py` — Thread-safe global variables guarded by locks.
- `main.py` — Application entry point coordinating bot and Telegram threads.

## Docs

- `QUICK_START.md` — Shortest path to run the bot.
- `SETUP_GUIDE.md` — Setup environment and troubleshooting guides.

## Disclaimer

Educational / demo use. Not production financial advice. Use with care.

