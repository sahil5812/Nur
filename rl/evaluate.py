"""
Evaluation Script for the PPO XAUUSD Trading Agent.

Loads a trained model, runs deterministic inference on the last 20 % of the
dataset (out-of-sample), computes performance metrics, and saves an equity
curve plot.

Usage:
    python -m rl.evaluate
    python -m rl.evaluate --model-path rl/models/ppo_xauusd.zip
"""

import argparse
import math
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from stable_baselines3 import PPO

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rl.trading_env import XAUUSDTradingEnv  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_max_drawdown(equity_curve: list[float]) -> float:
    """Return the maximum drawdown from peak equity (as a positive number)."""
    peak: float = -math.inf
    max_dd: float = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _compute_sharpe(
    trade_pnls: list[float],
    periods_per_year: int = 252 * 1440,
) -> float:
    """Annualised Sharpe ratio from per-trade PnL list.

    Uses *periods_per_year* = 252 trading days × 1440 minutes for
    minute-bar data.  Returns 0.0 when there are fewer than 2 trades.
    """
    if len(trade_pnls) < 2:
        return 0.0
    arr = np.array(trade_pnls, dtype=np.float64)
    mean_ret = float(np.mean(arr))
    std_ret = float(np.std(arr, ddof=1))
    if std_ret == 0.0:
        return 0.0
    return mean_ret / std_ret * math.sqrt(periods_per_year)


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------

def evaluate(model_path: str) -> dict[str, Any]:
    """Run a deterministic evaluation and return a metrics dictionary.

    The environment is created with its default CSV, but the evaluation
    loop only covers the **last 20 %** of the dataset by fast-forwarding
    through the first 80 % with HOLD actions before recording results.

    Args:
        model_path: Filesystem path to the saved PPO ``.zip`` model.

    Returns:
        Dictionary of computed performance metrics.
    """
    # ---- Load model --------------------------------------------------
    model_file = Path(model_path)
    if not model_file.is_file():
        print(f"ERROR: Model not found at {model_file}")
        sys.exit(1)

    model = PPO.load(str(model_file))
    print(f"✓ Model loaded from {model_file}")

    # ---- Build environment -------------------------------------------
    env = XAUUSDTradingEnv()

    # Determine split index (80 / 20) and configure OOS bounds
    total_steps: int = env._n
    split_idx: int = int(total_steps * 0.80)
    
    env.reset()
    env._start_idx = split_idx
    env.episode_length = total_steps - split_idx - 1
    obs = env._get_obs()

    print(f"  Total bars       : {total_steps:,}")
    print(f"  OOS start index  : {split_idx:,}")
    print(f"  OOS bars         : {env.episode_length:,}")

    # ---- Run episode -------------------------------------------------
    balance = 10000.0
    equity_curve: list[float] = [balance]
    trade_pnls: list[float] = []
    current_position: int = 0  # 0=flat, 1=long, 2=short
    entry_price: float = 0.0

    print(f"\n  → Entered OOS region at step {split_idx:,}")

    done: bool = False
    while not done:
        action_raw, _ = model.predict(obs, deterministic=True)
        action = int(action_raw)

        # Get close price prior to the step
        current_idx = env._start_idx + env._step_idx
        current_price = env._closes[min(current_idx, env._n - 1)]

        # Step the environment
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated

        # Detect position changes from the env's state
        new_position: int = env._position
        if new_position != current_position:
            # Position closed
            if current_position != 0 and new_position == 0:
                pnl = info.get("trade_pnl", info.get("forced_close_pnl", 0.0))
                trade_pnls.append(pnl)
                balance += pnl
            # Position opened
            if new_position != 0:
                entry_price = current_price
            current_position = new_position

        # Track floating equity at the end of this step
        next_idx = env._start_idx + env._step_idx
        next_price = env._closes[min(next_idx, env._n - 1)]
        if current_position == 0:
            equity = balance
        elif current_position == 1:
            equity = balance + (next_price - entry_price)
        else:
            equity = balance + (entry_price - next_price)

        equity_curve.append(equity)

    # ---- Compute metrics ---------------------------------------------
    total_trades = len(trade_pnls)
    wins = sum(1 for p in trade_pnls if p > 0)
    losses = sum(1 for p in trade_pnls if p <= 0)
    win_rate = wins / total_trades * 100.0 if total_trades else 0.0
    total_pnl = sum(trade_pnls)
    avg_pnl = total_pnl / total_trades if total_trades else 0.0
    max_dd = _compute_max_drawdown(equity_curve) if equity_curve else 0.0
    sharpe = _compute_sharpe(trade_pnls)

    metrics: dict[str, Any] = {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 2),
        "total_pnl": round(total_pnl, 4),
        "avg_pnl_per_trade": round(avg_pnl, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "oos_bars": len(equity_curve),
    }

    # ---- Print results -----------------------------------------------
    print("\n" + "=" * 60)
    print("  Out-of-Sample Evaluation Results")
    print("=" * 60)
    for key, val in metrics.items():
        label = key.replace("_", " ").title()
        print(f"  {label:<25s}: {val}")
    print("=" * 60)

    # ---- Plot equity curve -------------------------------------------
    if equity_curve:
        results_dir = Path(PROJECT_ROOT) / "rl" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        plot_path = results_dir / "equity_curve.png"

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(equity_curve, linewidth=0.8, color="#00e5ff", label="Equity")
        ax.set_title("XAUUSD PPO Agent – Out-of-Sample Equity Curve", fontsize=14)
        ax.set_xlabel("Step (OOS region)", fontsize=11)
        ax.set_ylabel("Equity", fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        fig.tight_layout()
        fig.savefig(str(plot_path), dpi=150)
        plt.close(fig)
        print(f"\n✓ Equity curve saved to {plot_path}")

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate a trained PPO agent on OOS XAUUSD data."
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=str(Path(PROJECT_ROOT) / "rl" / "models" / "ppo_xauusd.zip"),
        help="Path to the saved PPO model (default: rl/models/ppo_xauusd.zip).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry-point."""
    args = parse_args()
    evaluate(model_path=args.model_path)


if __name__ == "__main__":
    main()
