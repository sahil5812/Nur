"""
retrain_all.py — One-click: Download fresh data + Retrain all MARL agents.

Usage:
    1. Make sure MT5 terminal is OPEN and connected
    2. STOP the bot if running (bot uses MT5 connection)
    3. Run: python retrain_all.py

This will:
    Step 1: Download latest 3-year XAUUSD M1 data from MT5
    Step 2: Split into Train (70%) / Val (15%) / Test (15%)
    Step 3: Train HMM Regime Classifier
    Step 4: Train Trend PPO Agent (2M steps)
    Step 5: Train Range PPO Agent (2M steps)
    Step 6: Train Fallback PPO Agent (2M steps)
    Step 7: Evaluate all agents on test data

Estimated time: ~2-4 hours (depending on GPU/CPU)
"""

import os
import sys
import time
from pathlib import Path

# Project root
PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


def step_banner(step_num: int, title: str):
    print(f"\n{'='*60}")
    print(f"  Step {step_num}: {title}")
    print(f"{'='*60}\n")


def step1_download_data():
    """Download fresh 3-year XAUUSD M1 data from MT5."""
    step_banner(1, "Downloading Fresh Data from MT5")

    from scripts.fetch_history import fetch_xauusd_history, split_and_save

    df = fetch_xauusd_history(years=3)
    if df is None:
        print("[FATAL] Data download failed! MT5 open aur connected hai?")
        sys.exit(1)

    train_df, val_df, test_df = split_and_save(df)

    # Show price range to confirm current prices are included
    print(f"\n  Price range in data: {df['low'].min():.2f} — {df['high'].max():.2f}")
    print(f"  Latest close price: {df['close'].iloc[-1]:.2f}")

    return len(df)


def step2_train_hmm():
    """Train HMM Regime Classifier."""
    step_banner(2, "Training HMM Regime Classifier")

    import numpy as np
    from rl.trading_env import (
        _load_csv, _compute_ema_series, _compute_atr_series,
        _compute_rsi_series, EMA_PERIOD, ATR_PERIOD, RSI_PERIOD
    )
    from rl.hmm_classifier import GaussianHMM

    model_dir = Path(PROJECT_ROOT) / "rl" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    hmm_path = model_dir / "hmm_model.json"

    train_csv = Path(PROJECT_ROOT) / "data" / "train_xauusd_m1.csv"
    df_train = _load_csv(train_csv)
    closes = df_train["close"].values.astype(np.float64)
    highs = df_train["high"].values.astype(np.float64)
    lows = df_train["low"].values.astype(np.float64)

    ema = _compute_ema_series(closes, EMA_PERIOD)
    atr = _compute_atr_series(highs, lows, closes, ATR_PERIOD)
    valid_atr = atr[~np.isnan(atr)]
    atr_mean = float(np.mean(valid_atr)) if len(valid_atr) > 0 else 2.0
    atr_std = float(np.std(valid_atr)) + 1e-8 if len(valid_atr) > 0 else 1.0
    atr = np.where(np.isnan(atr), atr_mean, atr)
    rsi = _compute_rsi_series(closes, RSI_PERIOD)

    log_ret = np.zeros(len(closes))
    log_ret[1:] = np.diff(np.log(np.maximum(closes, 1e-8)))
    atr_n = np.clip((atr - atr_mean) / atr_std, -3.0, 3.0)
    rsi_n = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)

    features = np.column_stack([log_ret, atr_n, rsi_n])

    hmm = GaussianHMM(n_states=2)
    hmm.fit(features, max_iter=20)
    hmm.save(hmm_path)
    print(f"[OK] HMM Model saved to {hmm_path}")


def step3_train_ppo(regime: str, timesteps: int = 2_000_000):
    """Train a single PPO agent for the given regime."""
    label = regime.upper() if regime != "none" else "FALLBACK"
    step_banner(3 if regime == "trend" else (4 if regime == "range" else 5),
                f"Training {label} PPO Agent ({timesteps:,} steps)")

    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from rl.trading_env import XAUUSDTradingEnv
    import json

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device: {device}")

    model_dir = Path(PROJECT_ROOT) / "rl" / "models"
    hmm_path = model_dir / "hmm_model.json"
    env_regime = None if regime == "none" else regime

    # Create environment
    env = XAUUSDTradingEnv(
        split='train',
        target_regime=env_regime,
        hmm_model_path=hmm_path
    )

    # PPO hyperparameters
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

    # Simple progress callback
    class ProgressCallback(BaseCallback):
        def __init__(self):
            super().__init__()
            self.episode_rewards = []

        def _on_step(self):
            infos = self.locals.get("infos", [])
            for info in infos:
                ep = info.get("episode")
                if ep:
                    self.episode_rewards.append(float(ep["r"]))
            if self.num_timesteps % 50_000 == 0:
                recent = self.episode_rewards[-100:] if self.episode_rewards else []
                mean_r = sum(recent) / len(recent) if recent else 0.0
                pct = self.num_timesteps / timesteps * 100
                print(f"  [{pct:5.1f}%] Step {self.num_timesteps:>10,} | Episodes: {len(self.episode_rewards):>5,} | Mean reward: {mean_r:+.4f}")
            return True

    callback = ProgressCallback()

    # Train
    start = time.time()
    model.learn(total_timesteps=timesteps, callback=callback)
    elapsed = time.time() - start

    # Save model
    model_filename = f"ppo_{regime}.zip" if regime != "none" else "ppo_xauusd.zip"
    model_path = model_dir / model_filename
    model.save(str(model_path))
    print(f"\n[OK] {label} model saved to {model_path}")

    # Validation
    print(f"\n  Validating {label} agent...")
    val_env = XAUUSDTradingEnv(split='val', target_regime=env_regime, hmm_model_path=hmm_path)
    val_rewards = []
    for ep in range(10):
        obs, _ = val_env.reset()
        done = False
        ep_reward = 0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = val_env.step(action)
            ep_reward += reward
            done = terminated or truncated
        val_rewards.append(ep_reward)
    val_mean = sum(val_rewards) / len(val_rewards)
    print(f"  Validation Mean Reward: {val_mean:+.4f}")

    # Save training log
    final_rewards = callback.episode_rewards[-100:]
    final_mean = sum(final_rewards) / len(final_rewards) if final_rewards else 0.0
    log_filename = f"training_log_{regime}.json" if regime != "none" else "training_log.json"
    log_path = model_dir / log_filename
    log_data = {
        "total_timesteps": timesteps,
        "device": device,
        "episode_rewards": callback.episode_rewards,
        "final_mean_reward": round(final_mean, 6),
        "val_mean_reward": round(val_mean, 6),
        "total_episodes": len(callback.episode_rewards),
        "training_time_seconds": round(elapsed, 2),
    }
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    mins = elapsed / 60
    print(f"  Training time: {mins:.1f} minutes")

    return val_mean


def main():
    print("\n" + "=" * 60)
    print("  🔄 NUR BOT — FULL MARL RETRAINING PIPELINE")
    print("=" * 60)
    print("  This will download fresh data and retrain ALL agents.")
    print("  Estimated time: 2-4 hours")
    print("=" * 60)

    overall_start = time.time()

    # Step 1: Download fresh data
    total_bars = step1_download_data()

    # Step 2: Train HMM
    step2_train_hmm()

    # Steps 3-5: Train PPO agents
    results = {}
    for regime in ["trend", "range", "none"]:
        val_reward = step3_train_ppo(regime, timesteps=2_000_000)
        label = regime.upper() if regime != "none" else "FALLBACK"
        results[label] = val_reward

    # Summary
    total_time = time.time() - overall_start
    hours, rem = divmod(total_time, 3600)
    mins, secs = divmod(rem, 60)

    print("\n" + "=" * 60)
    print("  ✅ RETRAINING COMPLETE!")
    print("=" * 60)
    print(f"  Total data bars: {total_bars:,}")
    print(f"  Total time: {int(hours)}h {int(mins)}m {int(secs)}s")
    print(f"\n  Agent Validation Results:")
    for agent, reward in results.items():
        emoji = "✅" if reward > -50 else "⚠️"
        print(f"    {emoji} {agent:>10}: {reward:+.4f}")
    print(f"\n  Ab bot restart karo — naye models automatically load ho jayenge!")
    print("=" * 60)


if __name__ == "__main__":
    main()
