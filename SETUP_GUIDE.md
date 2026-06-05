# Nur Trading Agent — Setup & Run

## Prerequisites

- Python 3.10+ recommended (3.11 per project notes)
- MetaTrader 5 for live trading
- XAUUSD in Market Watch when trading live

## Install

From the `NUR` project directory:

```bash
pip install -r requirements.txt
```

## Backtesting (CSV, no MT5)

Uses `data/historical_xauusd_m1.csv`. Export from MT5 (History Center → XAUUSD M1) if you need data.

```bash
python backtest/engine_fixed.py
```

Or use `run_backtest.bat`.

## Live trading

- MT5 terminal running and logged in (demo recommended)
- XAUUSD visible in Market Watch

```bash
python main.py
```

Or `run_live.bat`. The live loop is implemented in `bot_engine.py` (loaded by `main.py` when configured accordingly).

## Configuration

- Live trading parameters: `bot_engine.py` (symbol, timeframe, EMA/ATR, volume, etc.)
- Backtest engine defaults: `backtest/engine_fixed.py` (`FixedBacktestEngine` config)
- Optional file bridge: `bridge/bridge.py`
- Optional MT5 wrapper: `live/mt5_bridge.py`

## Troubleshooting

- `MetaTrader5 not found` → `pip install MetaTrader5`
- `MT5 initialize failed` → ensure MT5 is running and logged in
- Missing data file → export M1 history to `data/historical_xauusd_m1.csv`

## Layout

```
NUR/
├── main.py
├── bot_engine.py
├── backtest/engine_fixed.py
├── bridge/bridge.py
├── core/
├── data/
├── integrations/
├── live/
├── logs/
└── utils/
```
