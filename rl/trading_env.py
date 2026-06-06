"""
rl/trading_env.py — Custom Gymnasium environment for XAUUSD M1 trading.

Observation space (7 features, normalized to [-1, 1]):
  [rsi, macd_hist, ema_distance_pct, atr_normalized, hour, session, position]

Action space: Discrete(3) → 0=HOLD, 1=BUY, 2=SELL

Reward:
  - Realized PnL (price points) on trade close
  - -0.1 per-step holding penalty
  - -2.0 invalid action penalty
"""

import sys
from pathlib import Path

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

from indicators.rsi import calculate_rsi
from indicators.macd import calculate_macd


# ─── Constants ────────────────────────────────────────────────
ACTION_HOLD = 0
ACTION_BUY  = 1
ACTION_SELL = 2

POS_FLAT  = 0
POS_LONG  = 1
POS_SHORT = 2

EPISODE_LENGTH = 1000
EMA_PERIOD     = 200
ATR_PERIOD     = 14
RSI_PERIOD     = 14
MACD_SLOW      = 26
MACD_SIGNAL    = 9
# Minimum warmup candles needed before the first valid observation
WARMUP = max(EMA_PERIOD, MACD_SLOW + MACD_SIGNAL, ATR_PERIOD + 1, RSI_PERIOD + 1)


def _load_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    Load XAUUSD M1 CSV, supporting both legacy semicolon-delimited files
    and the new comma-separated MT5-downloaded files.
    """
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        first_line = f.readline()
    
    if ';' in first_line:
        # Legacy semicolon-separated format
        df = pd.read_csv(
            csv_path,
            sep=";",
            header=0,
            names=["datetime", "open", "high", "low", "close", "volume", "col6", "col7"],
            dtype={
                "open": float, "high": float, "low": float,
                "close": float, "volume": float,
            },
            skiprows=1,
        )
        df["datetime"] = df["datetime"].str.strip('"')
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
        df = df.drop(columns=["col6", "col7"], errors="ignore")
    else:
        # New comma-separated format from fetch_history.py
        df = pd.read_csv(csv_path)
        if 'time' in df.columns:
            df = df.rename(columns={'time': 'datetime'})
        df["datetime"] = pd.to_datetime(df["datetime"])
        
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    return df


def _compute_ema_series(closes: np.ndarray, period: int) -> np.ndarray:
    """Compute a full EMA series across all candles."""
    ema = np.empty_like(closes)
    k = 2.0 / (period + 1)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
    return ema


def _compute_atr_series(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int
) -> np.ndarray:
    """Compute ATR series using true range."""
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)
    # Simple rolling mean ATR
    atr = np.empty(n)
    atr[:period] = np.nan
    atr[period] = np.mean(tr[:period])
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _compute_rsi_series(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Vectorised RSI matching the exact behavior of the project indicator in O(N)."""
    n = len(closes)
    rsi = np.full(n, 50.0)
    if n <= period:
        return rsi

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Use pandas rolling mean for fast O(N) sliding window average
    gains_series = pd.Series(gains)
    losses_series = pd.Series(losses)
    avg_gain = gains_series.rolling(window=period).mean().values
    avg_loss = losses_series.rolling(window=period).mean().values

    # Map back to closes series (index i in closes maps to i-1 in deltas/avg_gain)
    for i in range(period + 1, n):
        idx = i - 1
        ag = avg_gain[idx]
        al = avg_loss[idx]
        if np.isnan(ag) or np.isnan(al):
            rsi[i] = 50.0
        elif al == 0:
            rsi[i] = 100.0
        else:
            rs = ag / al
            rsi[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)
    return rsi


def _compute_macd_hist_series(closes: np.ndarray) -> np.ndarray:
    """Compute full MACD histogram series in O(N) matching the project indicator exactly."""
    n = len(closes)
    hist = np.zeros(n)
    if n < MACD_SLOW + MACD_SIGNAL:
        return hist

    # Compute full EMA series once
    fast_ema = _compute_ema_series(closes, 12)
    slow_ema = _compute_ema_series(closes, 26)
    macd_line = fast_ema - slow_ema

    # Compute signal line on the macd_line
    signal_line = _compute_ema_series(macd_line, 9)

    min_len = MACD_SLOW + MACD_SIGNAL
    for i in range(min_len, n):
        m = round(macd_line[i], 5)
        s = round(signal_line[i], 5)
        hist[i] = round(m - s, 5)
    return hist


def _get_session(hour: int) -> int:
    """0=Asian, 1=London, 2=NY, 3=Off-hours."""
    if 0 <= hour < 7:
        return 0   # Asian
    if 7 <= hour < 12:
        return 1   # London
    if 12 <= hour < 21:
        return 2   # NY
    return 3       # Off


class XAUUSDTradingEnv(gym.Env):
    """
    Gymnasium RL environment that replays XAUUSD M1 candles.

    Observation (7,): [rsi, macd_hist, ema_dist_pct, atr_norm, hour, session, position]
    All features normalized to approximately [-1, 1].

    Action Discrete(3): 0=HOLD, 1=BUY, 2=SELL
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        csv_path: str | Path | None = None,
        episode_length: int = EPISODE_LENGTH,
        split: str = 'train',  # 'train', 'val', 'test', or 'full'
        target_regime: str | None = None,
        hmm_model_path: str | Path | None = None,
    ):
        super().__init__()

        if csv_path is None:
            split_files = {
                'train': 'data/train_xauusd_m1.csv',
                'val':   'data/val_xauusd_m1.csv',
                'test':  'data/test_xauusd_m1.csv',
                'full':  'data/historical_xauusd_m1.csv'
            }
            csv_path = _PROJECT_ROOT / split_files.get(split, 'data/train_xauusd_m1.csv')
            
            # Fallback to full data if split file doesn't exist
            if not Path(csv_path).exists():
                csv_path = _PROJECT_ROOT / "data" / "historical_xauusd_m1.csv"
                
        self._csv_path = Path(csv_path)

        self.episode_length = episode_length
        self.target_regime = target_regime

        # Load and pre-compute
        self._df = _load_csv(self._csv_path)
        self._n = len(self._df)

        closes = self._df["close"].values.astype(np.float64)
        highs  = self._df["high"].values.astype(np.float64)
        lows   = self._df["low"].values.astype(np.float64)
        hours  = self._df["datetime"].dt.hour.values

        # Pre-computed indicator series (full dataset)
        self._closes = closes
        self._ema    = _compute_ema_series(closes, EMA_PERIOD)
        self._atr    = _compute_atr_series(highs, lows, closes, ATR_PERIOD)
        self._rsi    = _compute_rsi_series(closes, RSI_PERIOD)
        self._macd_h = _compute_macd_hist_series(closes)
        self._hours  = hours

        # ATR normalisation stats (computed on valid ATR range)
        valid_atr = self._atr[~np.isnan(self._atr)]
        self._atr_mean = float(np.mean(valid_atr))
        self._atr_std  = float(np.std(valid_atr)) + 1e-8

        # Build features for HMM state pre-calculation
        self._hmm_states = None
        if hmm_model_path is not None:
            hmm_path = Path(hmm_model_path)
            if hmm_path.exists():
                from rl.hmm_classifier import GaussianHMM
                hmm = GaussianHMM()
                hmm.load(hmm_path)
                
                log_ret = np.zeros(self._n)
                log_ret[1:] = np.diff(np.log(np.maximum(closes, 1e-8)))
                
                atr_n = np.clip((self._atr - self._atr_mean) / self._atr_std, -3.0, 3.0)
                atr_n = np.where(np.isnan(atr_n), 0.0, atr_n)
                
                rsi_n = np.clip((self._rsi - 50.0) / 50.0, -1.0, 1.0)
                
                features = np.column_stack([log_ret, atr_n, rsi_n])
                self._hmm_states = hmm.predict(features)

        # Gym spaces
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(7,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(3)

        # Episode state
        self._start_idx = WARMUP
        self._step_idx  = 0
        self._position  = POS_FLAT
        self._entry_price = 0.0
        self._total_reward = 0.0

    # ─── Gym API ──────────────────────────────────────────────

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)

        # Random start position (must leave room for WARMUP + episode_length)
        max_start = self._n - self.episode_length - 1
        min_start = WARMUP
        if max_start <= min_start:
            max_start = min_start + 1

        self._start_idx = self.np_random.integers(min_start, max_start)
        self._step_idx = 0
        self._position = POS_FLAT
        self._entry_price = 0.0
        self._total_reward = 0.0

        return self._get_obs(), {}

    def step(self, action: int):
        idx = self._start_idx + self._step_idx
        
        # Override action to HOLD if current market state does not match the target regime
        if self._hmm_states is not None and self.target_regime is not None:
            current_state = self._hmm_states[idx]  # 0 for Range, 1 for Trend
            if self.target_regime == 'trend' and current_state == 0:
                action = ACTION_HOLD
            elif self.target_regime == 'range' and current_state == 1:
                action = ACTION_HOLD

        price = self._closes[idx]
        reward = 0.0
        info = {}

        # ── Action execution ──────────────────────────────────
        if action == ACTION_BUY:
            if self._position == POS_FLAT:
                self._position = POS_LONG
                self._entry_price = price
            elif self._position == POS_SHORT:
                # Close short, realise PnL
                pnl = self._entry_price - price
                reward += pnl
                info["trade_pnl"] = pnl
                self._position = POS_FLAT
                self._entry_price = 0.0
            else:
                # Already long → invalid
                reward -= 2.0

        elif action == ACTION_SELL:
            if self._position == POS_FLAT:
                self._position = POS_SHORT
                self._entry_price = price
            elif self._position == POS_LONG:
                # Close long, realise PnL
                pnl = price - self._entry_price
                reward += pnl
                info["trade_pnl"] = pnl
                self._position = POS_FLAT
                self._entry_price = 0.0
            else:
                # Already short → invalid
                reward -= 2.0

        else:  # HOLD
            if self._position != POS_FLAT:
                reward -= 0.1  # holding penalty

        self._total_reward += reward
        self._step_idx += 1

        truncated = self._step_idx >= self.episode_length
        terminated = False

        # Force close at episode end
        if truncated and self._position != POS_FLAT:
            if self._position == POS_LONG:
                pnl = price - self._entry_price
            else:
                pnl = self._entry_price - price
            reward += pnl
            info["forced_close_pnl"] = pnl
            self._position = POS_FLAT

        obs = self._get_obs()
        return obs, reward, terminated, truncated, info

    # ─── Internal ─────────────────────────────────────────────

    def _get_obs(self) -> np.ndarray:
        idx = self._start_idx + self._step_idx
        # Clamp index to valid range
        idx = min(idx, self._n - 1)

        rsi    = self._rsi[idx]
        macd_h = self._macd_h[idx]
        close  = self._closes[idx]
        ema    = self._ema[idx]
        atr    = self._atr[idx] if not np.isnan(self._atr[idx]) else self._atr_mean
        hour   = self._hours[idx]

        # Normalise each feature to [-1, 1]
        rsi_norm     = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)
        macd_norm    = np.tanh(macd_h / max(atr, 0.01))
        ema_dist_pct = np.clip((close - ema) / max(ema, 1.0) * 100.0, -1.0, 1.0)
        atr_norm     = np.clip((atr - self._atr_mean) / self._atr_std, -1.0, 1.0)
        hour_norm    = hour / 23.0 * 2.0 - 1.0
        session      = _get_session(hour)
        session_norm = session / 3.0 * 2.0 - 1.0

        # Position encoding
        if self._position == POS_FLAT:
            pos_norm = 0.0
        elif self._position == POS_LONG:
            pos_norm = 1.0
        else:
            pos_norm = -1.0

        return np.array([
            rsi_norm, macd_norm, ema_dist_pct,
            atr_norm, hour_norm, session_norm, pos_norm,
        ], dtype=np.float32)


# ─── Quick self-test ──────────────────────────────────────────

if __name__ == "__main__":
    print("Testing XAUUSDTradingEnv...")
    env = XAUUSDTradingEnv()
    obs, info = env.reset()
    print(f"  Observation shape: {obs.shape}")
    print(f"  Observation range: [{obs.min():.3f}, {obs.max():.3f}]")
    print(f"  Total candles loaded: {env._n}")

    total_reward = 0.0
    for step in range(100):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break

    print(f"  Ran 100 steps, total reward: {total_reward:.2f}")
    print("  [OK] Environment works!")
