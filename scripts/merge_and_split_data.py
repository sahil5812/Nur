"""
scripts/merge_and_split_data.py — Combines 3.5-year Dukascopy Gold data with live MT5 recent bars.
Produces clean, standard, gap-free M1 dataset for Nur Bot MARL & Random Forest.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Set stdout encoding for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


def main():
    print("=" * 65)
    print(" [DATASET] Merging Multi-Year Data (2023 - 2026)")
    print("=" * 65)

    dukascopy_csv = PROJECT_ROOT / "scratch" / "download" / "xauusd-m1-bid-2023-01-01-2026-06-01.csv"
    if not dukascopy_csv.is_file():
        print(f"[FATAL] Dukascopy CSV not found at {dukascopy_csv}")
        sys.exit(1)

    print(f"1. Loading 3.5-year Dukascopy dataset: {dukascopy_csv.name}")
    df_duka = pd.read_csv(dukascopy_csv)
    print(f"   Raw Dukascopy rows: {len(df_duka):,}")

    df_duka["time"] = pd.to_datetime(df_duka["timestamp"], unit="ms")
    df_duka["open"] = df_duka["open"].round(2)
    df_duka["high"] = df_duka["high"].round(2)
    df_duka["low"] = df_duka["low"].round(2)
    df_duka["close"] = df_duka["close"].round(2)
    df_duka["tick_volume"] = 100
    df_duka["spread"] = 4
    df_duka["real_volume"] = 0

    # Filter out inactive weekend candles where high == low and no market activity
    active_mask = ~((df_duka["open"] == df_duka["high"]) & (df_duka["high"] == df_duka["low"]) & (df_duka["low"] == df_duka["close"]) & (df_duka["time"].dt.dayofweek >= 5))
    df_duka = df_duka[active_mask].copy()
    print(f"   Active market rows after removing weekend flats: {len(df_duka):,}")

    cols = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    df_duka = df_duka[cols]

    # 2. Fetch live recent bars from MT5
    print("\n2. Fetching recent live bars from MT5...")
    mt5_records = []
    if mt5.initialize():
        mt5.symbol_select("XAUUSD", True)
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 100000)
        if rates is not None and len(rates) > 0:
            df_mt5 = pd.DataFrame(rates)
            df_mt5["time"] = pd.to_datetime(df_mt5["time"], unit="s")
            df_mt5["real_volume"] = 0
            df_mt5 = df_mt5[cols]
            print(f"   Fetched {len(df_mt5):,} recent bars from MT5 ({df_mt5['time'].min()} -> {df_mt5['time'].max()})")
            mt5_records.append(df_mt5)
        mt5.shutdown()
    else:
        print("   MT5 connection skipped (using existing dataset)")

    # 3. Combine datasets
    if mt5_records:
        full_df = pd.concat([df_duka] + mt5_records, ignore_index=True)
    else:
        full_df = df_duka

    full_df.drop_duplicates(subset=["time"], keep="last", inplace=True)
    full_df.sort_values("time", inplace=True)
    full_df.reset_index(drop=True, inplace=True)

    total_bars = len(full_df)
    min_date = full_df["time"].min()
    max_date = full_df["time"].max()
    print(f"\n3. Final Combined Multi-Year Dataset:")
    print(f"   Total bars : {total_bars:,}")
    print(f"   Date range : {min_date} -> {max_date}")
    print(f"   Price span : ${full_df['low'].min():.2f} -> ${full_df['high'].max():.2f}")

    # 4. Split into Train (70%), Validation (15%), Test (15%)
    train_end = int(total_bars * 0.70)
    val_end = int(total_bars * 0.85)

    train_df = full_df.iloc[:train_end]
    val_df = full_df.iloc[train_end:val_end]
    test_df = full_df.iloc[val_end:]

    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("\n4. Saving datasets to disk...")
    # Convert time to string format for standard CSV
    full_df["time"] = full_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    train_df["time"] = train_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    val_df["time"] = val_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    test_df["time"] = test_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")

    train_path = data_dir / "train_xauusd_m1.csv"
    val_path = data_dir / "val_xauusd_m1.csv"
    test_path = data_dir / "test_xauusd_m1.csv"
    hist_path = data_dir / "historical_xauusd_m1.csv"

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    full_df.to_csv(hist_path, index=False)

    meta = {
        "total_bars": total_bars,
        "train_bars": len(train_df),
        "val_bars": len(val_df),
        "test_bars": len(test_df),
        "train_start": str(train_df["time"].iloc[0]),
        "train_end": str(train_df["time"].iloc[-1]),
        "val_start": str(val_df["time"].iloc[0]),
        "val_end": str(val_df["time"].iloc[-1]),
        "test_start": str(test_df["time"].iloc[0]),
        "test_end": str(test_df["time"].iloc[-1]),
        "price_min": float(full_df["low"].min()),
        "price_max": float(full_df["high"].max()),
        "downloaded_at": str(datetime.now()),
    }
    with open(data_dir / "dataset_info.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"   [OK] Train dataset (70%): {len(train_df):,} bars -> {train_path.name}")
    print(f"   [OK] Validation (15%)   : {len(val_df):,} bars -> {val_path.name}")
    print(f"   [OK] Test (15%)         : {len(test_df):,} bars -> {test_path.name}")
    print(f"   [OK] Full dataset       : {total_bars:,} bars -> {hist_path.name}")
    print(f"   [OK] Metadata saved to dataset_info.json")
    print("=" * 65)


if __name__ == "__main__":
    main()
