"""
scripts/train_rf_filter.py — Train & Prune Random Forest Meta-Filter.

Usage:
    python scripts/train_rf_filter.py

Performs:
    1. Loads train_xauusd_m1.csv
    2. Runs feature engineering (MTF Z-scores, ATR, RSI, MACD, session, HMM regime)
    3. Generates triple-barrier trade outcomes
    4. Dual Pruning:
       - Collinear feature pruning (|r| > 0.88)
       - MDI Feature Importance pruning (< 3% importance)
       - Decision Tree Cost-Complexity Pruning (ccp_alpha) + Depth constraints
    5. Evaluates out-of-sample precision lift via TimeSeriesSplit
    6. Saves pruned model to rl/models/rf_meta_filter.joblib
"""

import sys
import time
from pathlib import Path

# Configure utf-8 stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from intelligence.rf_filter import RandomForestMetaFilter
from rl.trading_env import _load_csv


def main():
    print("=" * 65)
    print(" [RANDOM FOREST] Meta-Filter Training & Pruning Pipeline")
    print("=" * 65)

    data_path = PROJECT_ROOT / "data" / "train_xauusd_m1.csv"
    if not data_path.is_file():
        # Fallback to historical if split not yet done
        data_path = PROJECT_ROOT / "data" / "historical_xauusd_m1.csv"
        if not data_path.is_file():
            print(f"[FATAL] Data file not found at {data_path}!")
            sys.exit(1)

    print(f"[DATA] Loading data from: {data_path.name}")
    start_time = time.time()
    df = _load_csv(data_path)
    print(f"  Loaded {len(df):,} M1 candles ({df['close'].iloc[0]:.2f} -> {df['close'].iloc[-1]:.2f})")

    # Instantiate filter with pruning settings
    rf_filter = RandomForestMetaFilter(
        min_prob_threshold=0.52,
        prune_importance_threshold=0.02,
        collinear_threshold=0.88,
        max_depth=8,
        min_samples_leaf=30,
        min_samples_split=60,
        ccp_alpha=0.0,
        n_estimators=100,
        random_state=42,
    )

    # Train and prune
    metrics = rf_filter.train(df, verbose=True)

    # Save to rl/models
    save_model_path = PROJECT_ROOT / "rl" / "models" / "rf_meta_filter.joblib"
    save_meta_path = PROJECT_ROOT / "rl" / "models" / "rf_filter_meta.json"
    rf_filter.save(save_model_path, save_meta_path)

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"[OK] Random Forest Meta-Filter Training Complete in {elapsed:.1f}s!")
    print(f"  Model saved to: {save_model_path}")
    print(f"  Active Pruned Features: {metrics['selected_features']}")
    print(f"  Baseline Win Rate: {metrics['baseline_win_rate']:.1%}")
    print(f"  Filtered Win Rate: {metrics['filtered_win_rate']:.1%} (Lift: {metrics['win_rate_lift_pct']:+.1f}%)")
    print("=" * 65)


if __name__ == "__main__":
    main()
