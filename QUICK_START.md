# Quick Start

## Backtesting (no MT5 required)

1. Double-click `setup.bat` (installs dependencies), or: `pip install -r requirements.txt`
2. Double-click `run_backtest.bat`, or from the `NUR` folder run:

```bash
python backtest/engine_fixed.py
```

Requires `data/historical_xauusd_m1.csv` (export M1 XAUUSD from MT5 History Center if missing).

## Live trading (MT5 required)

1. Open MetaTrader 5 (demo recommended), add **XAUUSD** to Market Watch, enable **Algo Trading**
2. Double-click `run_live.bat`, or: `python main.py` (from the `NUR` folder)

See `SETUP_GUIDE.md` for more detail.
