import MetaTrader5 as mt5

def spread_ok(symbol, max_spread=50):
    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        return False

    spread = (tick.ask - tick.bid) * 100

    return spread <= max_spread