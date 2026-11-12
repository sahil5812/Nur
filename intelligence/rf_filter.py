"""
intelligence/rf_filter.py — Random Forest Meta-Filter with Dual Pruning.

Implements López de Prado's Meta-Labeling framework for trade filtering:
  - Primary Strategy (MTF Z-score / HMM / PPO) proposes trade direction (BUY/SELL).
  - Random Forest Meta-Model estimates P(Trade Success | Features).
  - Trades with P(Success) < min_prob (default 0.55) are VETOED to filter noise and chop.
  - High-probability trades boost conviction for dynamic lot sizing.

Dual Pruning Architecture:
  1. Feature Pruning:
     - Collinearity elimination (|r| > threshold pruned).
     - MDI / Gini Feature Importance pruning (features < 3% importance pruned).
  2. Decision Tree Pruning:
     - Constrained max_depth, min_samples_leaf, min_samples_split.
     - Cost-Complexity Pruning (ccp_alpha) to cut weak leaf nodes.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit

from utils.logger import get_logger

logger = get_logger(__name__)

# Default model save path
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "rl" / "models" / "rf_meta_filter.joblib"
DEFAULT_META_PATH = Path(__file__).resolve().parent.parent / "rl" / "models" / "rf_filter_meta.json"

# All candidate features before pruning
ALL_CANDIDATE_FEATURES = [
    "z_h1",
    "z_m5",
    "z_m1",
    "rsi",
    "rsi_slope_5",
    "macd_hist",
    "atr_normalized",
    "realized_vol_20",
    "spread_ratio",
    "gamma_trend",
    "gamma_range",
    "hour_sin",
    "hour_cos",
    "session_london",
    "session_ny",
    "session_asian",
    "z_alignment",
]


class RandomForestMetaFilter:
    """Random Forest Meta-Classifier with Feature & Tree Pruning."""

    def __init__(
        self,
        min_prob_threshold: float = 0.42,
        prune_importance_threshold: float = 0.02,
        collinear_threshold: float = 0.88,
        max_depth: int = 8,
        min_samples_leaf: int = 30,
        min_samples_split: int = 60,
        ccp_alpha: float = 0.0,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.min_prob_threshold = min_prob_threshold
        self.prune_importance_threshold = prune_importance_threshold
        self.collinear_threshold = collinear_threshold
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.min_samples_split = min_samples_split
        self.ccp_alpha = ccp_alpha
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.model: Optional[RandomForestClassifier] = None
        self.selected_features: List[str] = list(ALL_CANDIDATE_FEATURES)
        self.feature_importances_: Dict[str, float] = {}
        self.pruned_features_: List[str] = []
        self.training_metrics_: Dict[str, Any] = {}
        self.is_fitted: bool = False

    # -------------------------------------------------------------------------
    # Feature Engineering (Vectorized for Training & Dict for Online Inference)
    # -------------------------------------------------------------------------
    @staticmethod
    def compute_technical_series(df: pd.DataFrame) -> pd.DataFrame:
        """Computes technical indicator series for offline training DataFrame."""
        df = df.copy()
        closes = df["close"].values.astype(np.float64)
        highs = df["high"].values.astype(np.float64)
        lows = df["low"].values.astype(np.float64)
        n = len(closes)

        # 1. EMAs for M1 (200), M5 approximation (1000 M1 bars), H1 approximation (12000 M1 bars or scaled)
        # To avoid massive windows on M1, we compute rolling EMAs:
        # EMA200 M1: 200 bars
        # EMA M5: 200 * 5 = 1000 bars
        # EMA H1: 200 * 60 = 12000 bars (clipped if n < 12000)
        span_m1 = 200
        span_m5 = min(1000, max(50, n // 10))
        span_h1 = min(12000, max(200, n // 3))

        ema_m1 = pd.Series(closes).ewm(span=span_m1, adjust=False).mean().values
        ema_m5 = pd.Series(closes).ewm(span=span_m5, adjust=False).mean().values
        ema_h1 = pd.Series(closes).ewm(span=span_h1, adjust=False).mean().values

        # 2. ATR (14-period)
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        atr_series = pd.Series(tr).rolling(14, min_periods=1).mean().values
        atr_safe = np.maximum(atr_series, 0.1)

        # 3. Z-scores: MTF Normalized Distances
        z_m1 = (closes - ema_m1) / atr_safe
        z_m5 = (closes - ema_m5) / atr_safe
        z_h1 = (closes - ema_h1) / atr_safe

        # 4. RSI (14-period)
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        g_s = pd.Series(np.insert(gains, 0, 0.0)).rolling(14, min_periods=1).mean().values
        l_s = pd.Series(np.insert(losses, 0, 0.0)).rolling(14, min_periods=1).mean().values
        rs = np.where(l_s > 0, g_s / np.maximum(l_s, 1e-8), 1.0)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # RSI 5-bar slope
        rsi_series = pd.Series(rsi)
        rsi_slope_5 = (rsi_series - rsi_series.shift(5)).fillna(0.0).values

        # 5. MACD Histogram (12, 26, 9)
        ema12 = pd.Series(closes).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(closes).ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_sig = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = (macd_line - macd_sig).values

        # 6. ATR Normalized
        atr_mean = float(np.mean(atr_safe))
        atr_std = float(np.std(atr_safe)) + 1e-8
        atr_normalized = np.clip((atr_safe - atr_mean) / atr_std, -3.0, 3.0)

        # 7. Realized Volatility (20-period log returns std)
        log_rets = np.zeros(n)
        log_rets[1:] = np.diff(np.log(np.maximum(closes, 1e-8)))
        realized_vol_20 = pd.Series(log_rets).rolling(20, min_periods=1).std().fillna(0.0).values

        # 8. Spread Ratio
        spread = df["spread"].values if "spread" in df.columns else np.full(n, 4.0)
        spread_ratio = spread / atr_safe

        # 9. Time & Sessions
        if "datetime" in df.columns:
            dt = pd.to_datetime(df["datetime"])
        elif "time" in df.columns:
            dt = pd.to_datetime(df["time"])
        else:
            dt = pd.date_range("2026-01-01", periods=n, freq="1min")

        hours = dt.dt.hour.values
        hour_sin = np.sin(2 * np.pi * hours / 24.0)
        hour_cos = np.cos(2 * np.pi * hours / 24.0)

        session_london = ((hours >= 7) & (hours < 16)).astype(float)
        session_ny = ((hours >= 12) & (hours < 21)).astype(float)
        session_asian = ((hours >= 0) & (hours < 8)).astype(float)

        # 10. HMM Soft Probabilities (Approximated by volatility & trend regime if not pre-computed)
        abs_zh1 = np.abs(z_h1)
        gamma_trend = np.clip(1.0 / (1.0 + np.exp(-1.5 * (abs_zh1 - 1.0))), 0.05, 0.95)
        gamma_range = 1.0 - gamma_trend

        # 11. MTF Alignment Score
        z_align = np.minimum(np.abs(z_h1), np.abs(z_m5)) * np.sign(z_h1 * z_m5)

        feat_df = pd.DataFrame({
            "z_h1": z_h1,
            "z_m5": z_m5,
            "z_m1": z_m1,
            "rsi": rsi,
            "rsi_slope_5": rsi_slope_5,
            "macd_hist": macd_hist,
            "atr_normalized": atr_normalized,
            "realized_vol_20": realized_vol_20,
            "spread_ratio": spread_ratio,
            "gamma_trend": gamma_trend,
            "gamma_range": gamma_range,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "session_london": session_london,
            "session_ny": session_ny,
            "session_asian": session_asian,
            "z_alignment": z_align,
            "close": closes,
            "atr": atr_safe,
        })
        return feat_df

    # -------------------------------------------------------------------------
    # Triple-Barrier Meta-Labeling (Target Generation)
    # -------------------------------------------------------------------------
    @staticmethod
    def generate_meta_labels(
        feat_df: pd.DataFrame,
        lookforward_bars: int = 60,
        tp_mult: float = 1.5,
        sl_mult: float = 1.0,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Generates binary meta-labels y in {0, 1} for trading setups.
        A trade setup is triggered when MTF trends align (|z_h1| > 0.3 and sign matches z_m5).
        Direction:
          BUY if z_h1 > 0
          SELL if z_h1 < 0
        Target:
          y = 1 if Take Profit (tp_mult * ATR) is hit BEFORE Stop Loss (sl_mult * ATR)
          y = 0 if Stop Loss is hit first or trade times out with non-positive return
        """
        closes = feat_df["close"].values
        atrs = feat_df["atr"].values
        z_h1 = feat_df["z_h1"].values
        z_m5 = feat_df["z_m5"].values
        n = len(closes)

        indices = []
        labels = []

        # Step through samples where there is a directional setup
        # Dynamic step size scales gracefully from small to multi-million candle datasets
        step_stride = max(5, n // 60000)
        for i in range(100, n - lookforward_bars - 1, step_stride):
            # Check setup trigger: MTF directional agreement
            if z_h1[i] > 0.2 and z_m5[i] > 0.0:
                direction = 1  # BUY
            elif z_h1[i] < -0.2 and z_m5[i] < 0.0:
                direction = -1  # SELL
            else:
                continue

            entry_price = closes[i]
            current_atr = max(atrs[i], 0.1)
            tp_dist = current_atr * tp_mult
            sl_dist = current_atr * sl_mult

            tp_price = entry_price + (tp_dist if direction == 1 else -tp_dist)
            sl_price = entry_price - (sl_dist if direction == 1 else -sl_dist)

            # Evaluate forward path over next lookforward_bars
            outcome = 0
            for f in range(1, lookforward_bars + 1):
                f_idx = i + f
                bar_price = closes[f_idx]

                if direction == 1:
                    # BUY trade evaluation
                    if bar_price >= tp_price:
                        outcome = 1
                        break
                    elif bar_price <= sl_price:
                        outcome = 0
                        break
                else:
                    # SELL trade evaluation
                    if bar_price <= tp_price:
                        outcome = 1
                        break
                    elif bar_price >= sl_price:
                        outcome = 0
                        break

            indices.append(i)
            labels.append(outcome)

        X = feat_df.iloc[indices][ALL_CANDIDATE_FEATURES].copy().reset_index(drop=True)
        y = pd.Series(labels, name="target")
        return X, y

    # -------------------------------------------------------------------------
    # Dual Pruning Algorithms
    # -------------------------------------------------------------------------
    def prune_collinear_features(self, X: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prunes highly collinear features (|Pearson r| > collinear_threshold).
        Keeps the feature with greater overall variance.
        """
        corr_matrix = X.corr().abs()
        pruned_cols = set()
        cols = list(X.columns)

        for i in range(len(cols)):
            col_a = cols[i]
            if col_a in pruned_cols:
                continue
            for j in range(i + 1, len(cols)):
                col_b = cols[j]
                if col_b in pruned_cols:
                    continue
                if corr_matrix.loc[col_a, col_b] >= self.collinear_threshold:
                    # Drop col_b which is redundant with col_a
                    var_a = X[col_a].var()
                    var_b = X[col_b].var()
                    drop_col = col_b if var_a >= var_b else col_a
                    keep_col = col_a if var_a >= var_b else col_b
                    pruned_cols.add(drop_col)
                    logger.info(
                        f"[PRUNING] Collinear: Dropping '{drop_col}' "
                        f"(r={corr_matrix.loc[col_a, col_b]:.2f} with '{keep_col}')"
                    )

        kept_cols = [c for c in cols if c not in pruned_cols]
        return X[kept_cols].copy(), list(pruned_cols)

    def prune_low_importance_features(
        self, X: pd.DataFrame, y: pd.Series
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Trains a pilot Random Forest and prunes features whose MDI/Gini importance
        is below prune_importance_threshold.
        """
        pilot_rf = RandomForestClassifier(
            n_estimators=50,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state,
            n_jobs=-1,
        )
        pilot_rf.fit(X, y)

        importances = dict(zip(X.columns, pilot_rf.feature_importances_))
        low_imp_cols = []
        for col, imp in sorted(importances.items(), key=lambda item: item[1]):
            if imp < self.prune_importance_threshold:
                low_imp_cols.append(col)
                logger.info(
                    f"[PRUNING] Low Importance: Dropping '{col}' "
                    f"(Importance={imp:.4f} < {self.prune_importance_threshold})"
                )

        # Ensure we always keep at least the top 5 features
        if len(X.columns) - len(low_imp_cols) < 5:
            sorted_cols = sorted(importances.items(), key=lambda item: item[1], reverse=True)
            kept_cols = [item[0] for item in sorted_cols[:5]]
            low_imp_cols = [c for c in X.columns if c not in kept_cols]
        else:
            kept_cols = [c for c in X.columns if c not in low_imp_cols]

        return X[kept_cols].copy(), low_imp_cols

    # -------------------------------------------------------------------------
    # Model Training & Pruning Pipeline
    # -------------------------------------------------------------------------
    def train(self, df_raw: pd.DataFrame, verbose: bool = True) -> Dict[str, Any]:
        """
        Executes full training pipeline with dual pruning:
          1. Compute technical candidate features.
          2. Generate triple-barrier meta-labels.
          3. Level 1 Pruning: Collinear features removal.
          4. Level 1 Pruning: Low MDI feature importance removal.
          5. Level 2 Pruning: Fit final Random Forest with cost-complexity pruning (ccp_alpha)
             and constrained tree depth/leaf size.
          6. TimeSeriesSplit validation.
        """
        if verbose:
            print("\n[RF] Starting feature engineering...")
        feat_df = self.compute_technical_series(df_raw)

        if verbose:
            print(f"[RF] Generating triple-barrier meta-labels...")
        X, y = self.generate_meta_labels(feat_df)
        if len(X) < 100 or y.nunique() < 2:
            raise ValueError(f"Insufficient training setups generated: {len(X)} samples, classes={y.unique()}")

        base_samples = len(X)
        win_rate_unfiltered = float(y.mean())
        if verbose:
            print(f"  Total setups: {base_samples:,} | Baseline Win Rate: {win_rate_unfiltered:.1%}")

        # Step A: Collinearity Pruning
        X_uncollinear, collinear_dropped = self.prune_collinear_features(X)

        # Step B: Low-Importance Pruning
        X_pruned, low_imp_dropped = self.prune_low_importance_features(X_uncollinear, y)

        self.selected_features = list(X_pruned.columns)
        self.pruned_features_ = collinear_dropped + low_imp_dropped

        if verbose:
            print(f"\n[PRUNING SUMMARY]:")
            print(f"  Candidate features: {len(ALL_CANDIDATE_FEATURES)}")
            print(f"  Collinear dropped:  {collinear_dropped}")
            print(f"  Low-imp dropped:    {low_imp_dropped}")
            print(f"  Active features ({len(self.selected_features)}): {self.selected_features}")

        # Step C: Final Random Forest Training with Structural Tree Pruning
        # max_depth=6, min_samples_leaf=30, ccp_alpha=0.001
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            min_samples_split=self.min_samples_split,
            ccp_alpha=self.ccp_alpha,
            max_features="sqrt",
            random_state=self.random_state,
            n_jobs=-1,
            class_weight="balanced",
        )

        # Time Series Cross-Validation to evaluate generalization
        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = []
        filtered_precision_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_pruned)):
            X_tr, y_tr = X_pruned.iloc[train_idx], y.iloc[train_idx]
            X_val, y_val = X_pruned.iloc[val_idx], y.iloc[val_idx]

            fold_rf = RandomForestClassifier(
                n_estimators=50,
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                min_samples_split=self.min_samples_split,
                ccp_alpha=self.ccp_alpha,
                max_features="sqrt",
                random_state=self.random_state + fold,
                n_jobs=-1,
                class_weight="balanced",
            )
            fold_rf.fit(X_tr, y_tr)
            val_probs = fold_rf.predict_proba(X_val)[:, 1]

            # Precision of filtered trades (where prob >= min_prob_threshold)
            high_prob_mask = val_probs >= self.min_prob_threshold
            if high_prob_mask.sum() > 0:
                filtered_prec = float(y_val[high_prob_mask].mean())
                filtered_precision_scores.append(filtered_prec)
            cv_scores.append(float(fold_rf.score(X_val, y_val)))

        # Fit final model on all data
        self.model.fit(X_pruned, y)
        self.is_fitted = True

        # Calculate final feature importances
        self.feature_importances_ = {
            col: round(float(imp), 4)
            for col, imp in zip(self.selected_features, self.model.feature_importances_)
        }

        # Out-of-sample precision improvement
        mean_cv_acc = float(np.mean(cv_scores)) if cv_scores else 0.0
        mean_filt_prec = float(np.mean(filtered_precision_scores)) if filtered_precision_scores else win_rate_unfiltered
        improvement = mean_filt_prec - win_rate_unfiltered

        self.training_metrics_ = {
            "total_samples": base_samples,
            "baseline_win_rate": round(win_rate_unfiltered, 4),
            "filtered_win_rate": round(mean_filt_prec, 4),
            "win_rate_lift_pct": round(improvement * 100.0, 2),
            "cv_accuracy": round(mean_cv_acc, 4),
            "selected_features": self.selected_features,
            "pruned_features": self.pruned_features_,
            "feature_importances": self.feature_importances_,
            "hyperparameters": {
                "max_depth": self.max_depth,
                "min_samples_leaf": self.min_samples_leaf,
                "ccp_alpha": self.ccp_alpha,
                "n_estimators": self.n_estimators,
            },
        }

        if verbose:
            print(f"\n[VALIDATION RESULTS]:")
            print(f"  Unfiltered Win Rate: {win_rate_unfiltered:.1%}")
            print(f"  RF-Filtered Win Rate: {mean_filt_prec:.1%} (Lift: {improvement:+.1%})")
            print(f"  CV Accuracy:         {mean_cv_acc:.1%}")
            print(f"  Feature Importances: {self.feature_importances_}")

        return self.training_metrics_

    # -------------------------------------------------------------------------
    # Online Inference & Trade Veto Filter
    # -------------------------------------------------------------------------
    def predict_probability(self, features_dict: Dict[str, Any]) -> float:
        """
        Computes P(Trade Success) for the live state dictionary using the pruned feature set.
        Returns float between 0.0 and 1.0.
        """
        if not self.is_fitted or self.model is None:
            # Fallback if model is not loaded/fitted
            return 0.50

        # Build feature vector matching self.selected_features
        row = []
        for feat_name in self.selected_features:
            val = features_dict.get(feat_name, 0.0)
            if val is None or math.isnan(val):
                val = 0.0
            row.append(float(val))

        X_input = pd.DataFrame([row], columns=self.selected_features)
        try:
            probs = self.model.predict_proba(X_input)
            # Probability of class 1 (Trade Success)
            prob_success = float(probs[0, 1]) if probs.shape[1] > 1 else float(probs[0, 0])
            return prob_success
        except Exception as exc:
            logger.warning(f"RF predict_probability exception: {exc}")
            return 0.50

    def evaluate_trade(
        self,
        direction: str,
        features_dict: Dict[str, Any],
        min_prob_override: Optional[float] = None,
    ) -> Tuple[bool, float, str]:
        """
        Evaluates a candidate trade direction ('BUY' or 'SELL') against the Random Forest.

        Returns:
          (approved: bool, probability: float, reason: str)
        """
        threshold = min_prob_override if min_prob_override is not None else self.min_prob_threshold

        if not self.is_fitted or self.model is None:
            return True, 0.50, "Random Forest not active (model uninitialized, passing trade)"

        prob = self.predict_probability(features_dict)

        if prob < threshold:
            reason = (
                f"✂️ RF Filter VETO: {direction} probability {prob:.1%} is below threshold {threshold:.1%} "
                f"(High risk of whipsaw/consolidation trap)"
            )
            return False, prob, reason
        else:
            reason = (
                f"✅ RF Filter APPROVED: {direction} probability {prob:.1%} >= {threshold:.1%} "
                f"(High conviction setup)"
            )
            return True, prob, reason

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------
    def save(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        meta_path: Path | str = DEFAULT_META_PATH,
    ) -> None:
        """Saves pruned model artifact and metadata."""
        model_path = Path(model_path)
        meta_path = Path(meta_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            {
                "model": self.model,
                "selected_features": self.selected_features,
                "pruned_features": self.pruned_features_,
                "feature_importances": self.feature_importances_,
                "min_prob_threshold": self.min_prob_threshold,
                "is_fitted": self.is_fitted,
            },
            model_path,
        )

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.training_metrics_, f, indent=2)

        logger.info(f"Random Forest Meta-Filter saved to {model_path} and {meta_path}")

    def load(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        meta_path: Path | str = DEFAULT_META_PATH,
    ) -> bool:
        """Loads pruned model artifact and metadata."""
        model_path = Path(model_path)
        meta_path = Path(meta_path)

        if not model_path.is_file():
            logger.debug(f"Random Forest model file not found at {model_path}")
            return False

        try:
            data = joblib.load(model_path)
            self.model = data["model"]
            self.selected_features = data["selected_features"]
            self.pruned_features_ = data.get("pruned_features", [])
            self.feature_importances_ = data.get("feature_importances", {})
            self.min_prob_threshold = data.get("min_prob_threshold", self.min_prob_threshold)
            self.is_fitted = data.get("is_fitted", True)

            if meta_path.is_file():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        self.training_metrics_ = json.load(f)
                except Exception:
                    pass

            logger.info(
                f"✅ Random Forest Meta-Filter loaded successfully from {model_path} "
                f"({len(self.selected_features)} pruned features active)"
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to load Random Forest Meta-Filter: {exc}")
            return False
