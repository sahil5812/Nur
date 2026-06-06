import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rl.agent import RLAgent

print("Initializing RLAgent...")
agent = RLAgent()

# Build a typical strong BUY state dictionary
buy_state = {
    "rsi": 30.0,                 # Oversold (Buy signal)
    "macd_hist": 2.5,            # Bullish momentum
    "ema_distance_pct": -1.2,    # Pullback distance below EMA
    "atr_normalized": 0.5,
    "hour": 14,                  # London/NY overlap
    "session": 1,                # London
    "position": 0,               # Flat
}

# Build a typical strong SELL state dictionary
sell_state = {
    "rsi": 70.0,                 # Overbought (Sell signal)
    "macd_hist": -2.5,           # Bearish momentum
    "ema_distance_pct": 1.2,     # Above EMA
    "atr_normalized": 0.5,
    "hour": 14,
    "session": 1,
    "position": 0,
}

print("\n--- Diagnostic Predictions ---")
buy_action = agent.predict(buy_state)
buy_conf = agent.get_confidence(buy_state)
print(f"BUY State Prediction  : {buy_action} (Confidences: {buy_conf})")

sell_action = agent.predict(sell_state)
sell_conf = agent.get_confidence(sell_state)
print(f"SELL State Prediction : {sell_action} (Confidences: {sell_conf})")
