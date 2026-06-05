# RL Trading Agent for Nur Bot

Reinforcement Learning module using **PPO (Proximal Policy Optimization)** from
stable-baselines3 to learn XAUUSD M1 trading decisions.

## Architecture

```
rl/
├── __init__.py         # Package marker
├── trading_env.py      # Custom Gymnasium environment
├── train.py            # PPO training pipeline (GPU auto-detect)
├── agent.py            # Inference wrapper (RLAgent class)
├── evaluate.py         # Out-of-sample backtester
├── models/             # Saved model weights
│   ├── ppo_xauusd.zip
│   └── training_log.json
├── results/            # Evaluation outputs
│   └── equity_curve.png
└── README.md           # This file
```

## How It Works

### Observation Space (7 features, normalized to [-1, 1])

| Index | Feature           | Description                         |
|-------|-------------------|-------------------------------------|
| 0     | RSI(14)           | `(rsi - 50) / 50`                  |
| 1     | MACD histogram    | `tanh(histogram / ATR)`             |
| 2     | EMA distance %    | `(price - EMA200) / EMA200 × 100`  |
| 3     | ATR normalized    | `(ATR - mean) / std`                |
| 4     | Hour of day       | `hour / 23 × 2 - 1`                |
| 5     | Trading session   | Asian/London/NY/Off encoded         |
| 6     | Position          | Flat=0, Long=1, Short=-1            |

### Action Space
- `0` = HOLD — do nothing
- `1` = BUY — open long or close short
- `2` = SELL — open short or close long

### Reward Function
- **Realized PnL** in price points when a position is closed
- **-0.1** per-step holding penalty (encourages decisive exits)
- **-2.0** invalid action penalty (e.g., buying when already long)

## Quick Start

### 1. Install Dependencies

```bash
pip install stable-baselines3 gymnasium matplotlib shimmy
```

### 2. Train the Model

```bash
# Full training (2M steps, ~30-60 min on GPU)
python rl/train.py

# Quick sanity check (10k steps, ~30 seconds)
python rl/train.py --timesteps 10000
```

GPU is auto-detected. Training saves:
- `rl/models/ppo_xauusd.zip` — model weights
- `rl/models/training_log.json` — training statistics

### 3. Evaluate (Out-of-Sample)

```bash
python rl/evaluate.py
```

Tests on the **last 20%** of CSV data (data the model never saw during training).
Prints win rate, PnL, drawdown, Sharpe ratio. Saves equity curve to
`rl/results/equity_curve.png`.

### 4. Bot Integration

The RL agent integrates with `bot_engine.py` as an **augmentation layer**:

```
Existing Score System → RL Agent → Trade Decision
```

- RL acts as a **veto/confirmation gate**
- Only triggers trades when existing score ≥ 60 AND RL agrees
- If RL says HOLD → trade is blocked regardless of score
- All existing risk management (daily limits, trailing stops, paper trading) remains unchanged

No code changes needed — once a model is trained and saved, the bot engine
automatically loads and uses it on next startup.

## Training Tips

- Start with `--timesteps 10000` to verify the pipeline works
- Watch the mean episode reward — it should trend upward during training
- Gold (XAUUSD) is volatile; expect the model to be conservative initially
- The model learns on 80% of data; evaluate on the remaining 20%
- Retrain periodically as market conditions change
