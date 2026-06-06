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
    parser.add_argument(
        "--n-envs",
        type=int,
        default=4,
        help="Number of parallel environments to run (default: 4). Use 1 to disable parallelization.",
    )
    parser.add_argument(
        "--target-regime",
        type=str,
        default="none",
        choices=["none", "trend", "range"],
        help="Target regime filter for specialized training (none, trend, range).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry-point: build env, train PPO, save model & logs."""
    import numpy as np
    from rl.trading_env import (
        _load_csv, _compute_ema_series, _compute_atr_series,
        _compute_rsi_series, EMA_PERIOD, ATR_PERIOD, RSI_PERIOD
    )

    args = parse_args()
    total_timesteps: int = args.timesteps
    n_envs: int = args.n_envs
    target_regime: str = args.target_regime

    print("=" * 60)
    print("  3-Agent MARL Training – XAUUSD Trading Agent")
    print("=" * 60)
    print(f"  Device          : {device}")
    print(f"  Total timesteps : {total_timesteps:,}")
    print(f"  Parallel Envs   : {n_envs}")
    print(f"  Target Regime   : {target_regime.upper()}")
    print("=" * 60)

    model_dir = Path(PROJECT_ROOT) / "rl" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    hmm_model_path = model_dir / "hmm_model.json"

    # ---- HMM Fitting (Phase 1) ---------------------------------------
    print("\nTraining HMM Classifier to detect market regimes...")
    train_csv = Path(PROJECT_ROOT) / "data" / "train_xauusd_m1.csv"
    if not train_csv.exists():
        train_csv = Path(PROJECT_ROOT) / "data" / "historical_xauusd_m1.csv"

    if train_csv.exists():
        df_train = _load_csv(train_csv)
        closes_tr = df_train["close"].values.astype(np.float64)
        highs_tr = df_train["high"].values.astype(np.float64)
        lows_tr = df_train["low"].values.astype(np.float64)

        ema_tr = _compute_ema_series(closes_tr, EMA_PERIOD)
        atr_tr = _compute_atr_series(highs_tr, lows_tr, closes_tr, ATR_PERIOD)
        valid_atr = atr_tr[~np.isnan(atr_tr)]
        atr_mean_tr = float(np.mean(valid_atr)) if len(valid_atr) > 0 else 2.0
        atr_std_tr = float(np.std(valid_atr)) + 1e-8 if len(valid_atr) > 0 else 1.0

        atr_tr = np.where(np.isnan(atr_tr), atr_mean_tr, atr_tr)
        rsi_tr = _compute_rsi_series(closes_tr, RSI_PERIOD)

        log_ret = np.zeros(len(closes_tr))
        log_ret[1:] = np.diff(np.log(np.maximum(closes_tr, 1e-8)))

        atr_n = np.clip((atr_tr - atr_mean_tr) / atr_std_tr, -3.0, 3.0)
        rsi_n = np.clip((rsi_tr - 50.0) / 50.0, -1.0, 1.0)

        features = np.column_stack([log_ret, atr_n, rsi_n])

        from rl.hmm_classifier import GaussianHMM
        hmm = GaussianHMM(n_states=2)
        hmm.fit(features, max_iter=20)
        hmm.save(hmm_model_path)
        print(f"[OK] HMM Model saved to {hmm_model_path}")
    else:
        print("[WARNING] Training CSV not found. Skipping HMM fitting.")

    # ---- Environment -------------------------------------------------
    env_regime = None if target_regime == "none" else target_regime
    
    if n_envs > 1:
        from stable_baselines3.common.env_util import make_vec_env
        from stable_baselines3.common.vec_env import SubprocVecEnv
        
        def make_env():
            return XAUUSDTradingEnv(
                split='train',
                target_regime=env_regime,
                hmm_model_path=hmm_model_path
            )
            
        env = make_vec_env(make_env, n_envs=n_envs, vec_env_cls=SubprocVecEnv)
    else:
        env = XAUUSDTradingEnv(
            split='train',
            target_regime=env_regime,
            hmm_model_path=hmm_model_path
        )

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
    model_filename = f"ppo_{target_regime}.zip" if target_regime != "none" else "ppo_xauusd.zip"
    model_path = model_dir / model_filename
    model.save(str(model_path))
    print(f"\n[OK] Model saved to {model_path}")

    # ---- Validation --------------------------------------------------
    print("\nValidation set pe check kar raha hoon...")
    val_env = XAUUSDTradingEnv(
        split='val',
        target_regime=env_regime,
        hmm_model_path=hmm_model_path
    )
    val_rewards = []
    for _ in range(10):
        obs, _ = val_env.reset()
        done = False
        ep_reward = 0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = val_env.step(action)
            ep_reward += reward
            done = terminated or truncated
        val_rewards.append(ep_reward)
    
    val_mean_reward = sum(val_rewards) / len(val_rewards)
    print(f"Validation Mean Reward: {val_mean_reward:.4f}")

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
        "val_mean_reward": round(val_mean_reward, 6),
        "total_episodes": len(callback.episode_rewards),
        "training_time_seconds": round(elapsed, 2),
    }

    log_filename = f"training_log_{target_regime}.json" if target_regime != "none" else "training_log.json"
    log_path = model_dir / log_filename
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)
    print(f"[OK] Training log saved to {log_path}")

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
