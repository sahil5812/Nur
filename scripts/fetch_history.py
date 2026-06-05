import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fetch_xauusd_history(years=3):
    print("MT5 se connect ho raha hoon...")
    
    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return None
    
    symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_M1
    end_time = datetime.now()
    start_time = end_time - timedelta(days=365 * years)
    
    print(f"Downloading {symbol} M1 data from {start_time.date()} to {end_time.date()}...")
    
    # Fetch in chunks to avoid timeout
    all_data = []
    chunk_start = start_time
    chunk_days = 30  # 30 days per chunk
    
    while chunk_start < end_time:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end_time)
        
        rates = mt5.copy_rates_range(
            symbol, timeframe, chunk_start, chunk_end
        )
        
        if rates is not None and len(rates) > 0:
            all_data.append(pd.DataFrame(rates))
            print(f"  [OK] {chunk_start.date()} -> {chunk_end.date()} | {len(rates)} bars")
        
        chunk_start = chunk_end
    
    mt5.shutdown()
    
    if not all_data:
        print("[ERROR] Koi data nahi mila!")
        return None
    
    # Combine all chunks
    df = pd.concat(all_data, ignore_index=True)
    df.drop_duplicates(subset=['time'], inplace=True)
    df.sort_values('time', inplace=True)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"\nTotal bars downloaded: {len(df)}")
    print(f"   Date range: {df['time'].min()} -> {df['time'].max()}")
    
    return df

def split_and_save(df):
    """Split into Train/Validation/Test and save"""
    
    total = len(df)
    train_end = int(total * 0.70)
    val_end   = int(total * 0.85)
    
    train_df = df.iloc[:train_end]
    val_df   = df.iloc[train_end:val_end]
    test_df  = df.iloc[val_end:]
    
    os.makedirs('data', exist_ok=True)
    
    # Save full dataset
    full_path = 'data/historical_xauusd_m1.csv'
    df.to_csv(full_path, index=False)
    
    # Save splits
    train_df.to_csv('data/train_xauusd_m1.csv', index=False)
    val_df.to_csv('data/val_xauusd_m1.csv',   index=False)
    test_df.to_csv('data/test_xauusd_m1.csv',  index=False)
    
    print(f"\nData Split Complete:")
    print(f"   Training   (70%): {len(train_df):,} bars -> data/train_xauusd_m1.csv")
    print(f"   Validation (15%): {len(val_df):,} bars -> data/val_xauusd_m1.csv")
    print(f"   Testing    (15%): {len(test_df):,} bars -> data/test_xauusd_m1.csv")
    print(f"   Full data       : {len(df):,} bars -> data/historical_xauusd_m1.csv")
    
    # Save metadata
    import json
    meta = {
        "total_bars": total,
        "train_bars": len(train_df),
        "val_bars": len(val_df),
        "test_bars": len(test_df),
        "train_start": str(train_df['time'].min()),
        "train_end": str(train_df['time'].max()),
        "val_start": str(val_df['time'].min()),
        "val_end": str(val_df['time'].max()),
        "test_start": str(test_df['time'].min()),
        "test_end": str(test_df['time'].max()),
        "downloaded_at": str(datetime.now())
    }
    with open('data/dataset_info.json', 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"\nMetadata saved: data/dataset_info.json")
    return train_df, val_df, test_df

if __name__ == "__main__":
    print("=" * 50)
    print("  NUR BOT - Historical Data Fetcher")
    print("=" * 50)
    
    # Download 3 years of data
    df = fetch_xauusd_history(years=3)
    
    if df is not None:
        train_df, val_df, test_df = split_and_save(df)
        print("\nDone! Ab MARL training ke liye data ready hai.")
    else:
        print("\nFailed. MT5 open aur connected hai?")
