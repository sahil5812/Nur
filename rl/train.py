"""
PPO Training Script for XAUUSD Trading Agent.

Trains a Proximal Policy Optimization agent on the XAUUSD trading environment
using Stable-Baselines3. Supports GPU acceleration when available and provides
real-time training progress via a custom callback.

Usage:
    python -m rl.train --timesteps 2000000
"""

import argparse
import json
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
import time
from pathlib import Path
from typing import Any

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

# ---------------------------------------------------------------------------
# Project root on sys.path so `rl.*` and `utils.*` imports resolve correctly.
# ---------------------------------------------------------------------------
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rl.trading_env import XAUUSDTradingEnv  # noqa: E402


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------
device: str = "cuda" if torch.cuda.is_available() else "cpu"


class TrainingProgressCallback(BaseCallback):
    """Custom callback that logs training progress every *print_freq* steps.

    Attributes:
        print_freq: How often (in timesteps) to print a progress line.
        episode_rewards: Running list of episode rewards collected so far.
    """

    def __init__(self, print_freq: int = 10_000, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.print_freq: int = print_freq
        self.episode_rewards: list[float] = []

    # ------------------------------------------------------------------
    def _on_step(self) -> bool:
        """Called after every environment step."""
        # Collect episode rewards from the Monitor wrapper (if available).
        infos: list[dict[str, Any]] = self.locals.get("infos", [])
        for info in infos:
            ep_info = info.get("episode")
            if ep_info is not None:
                self.episode_rewards.append(float(ep_info["r"]))

        # Periodic progress printout.
        if self.num_timesteps % self.print_freq == 0:
            recent = self.episode_rewards[-100:] if self.episode_rewards else []
            mean_rew = sum(recent) / len(recent) if recent else 0.0
            print(
                f"[Step {self.num_timesteps:>10,}]  "
                f"Episodes: {len(self.episode_rewards):>6,}  |  "
                f"Mean reward (last 100): {mean_rew:+.4f}"
            )

        return True  # Returning False would stop training.


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Train a PPO agent on XAUUSD trading environment."
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=2_000_000,
        help="Total training timesteps (default: 2,000,000).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry-point: build env, train PPO, save model & logs."""
    args = parse_args()
    total_timesteps: int = args.timesteps

    print("=" * 60)
    print("  PPO Training – XAUUSD Trading Agent")
    print("=" * 60)
    print(f"  Device          : {device}")
    print(f"  Total timesteps : {total_timesteps:,}")
    print("=" * 60)

    # ---- Environment -------------------------------------------------
    env = XAUUSDTradingEnv()

    # ---- PPO hyperparameters -----------------------------------------
    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        verbose=1,
        device=device,
    )

    # ---- Callback ----------------------------------------------------
    callback = TrainingProgressCallback(print_freq=10_000)

    # ---- Train -------------------------------------------------------
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    elapsed = time.time() - start_time

    # ---- Save model --------------------------------------------------
    model_dir = Path(PROJECT_ROOT) / "rl" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "ppo_xauusd.zip"
    model.save(str(model_path))
    print(f"\n✓ Model saved to {model_path}")

    # ---- Save training log -------------------------------------------
    final_rewards = callback.episode_rewards[-100:]
    final_mean = (
        sum(final_rewards) / len(final_rewards) if final_rewards else 0.0
    )

    log_data: dict[str, Any] = {
        "total_timesteps": total_timesteps,
        "device": device,
        "episode_rewards": callback.episode_rewards,
        "final_mean_reward": round(final_mean, 6),
        "total_episodes": len(callback.episode_rewards),
        "training_time_seconds": round(elapsed, 2),
    }

    log_path = model_dir / "training_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)
    print(f"✓ Training log saved to {log_path}")

    # ---- Summary -----------------------------------------------------
    hours, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    print(
        f"\n  Total training time: {int(hours):02d}h {int(mins):02d}m {secs:05.2f}s"
    )
    print(f"  Final mean reward (last 100 eps): {final_mean:+.4f}")
    print("  Done.\n")


if __name__ == "__main__":
    main()
