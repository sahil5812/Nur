"""
tests/test_rf_filter.py — Unit tests for Random Forest Meta-Filter and Pruning.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.rf_filter import (
    ALL_CANDIDATE_FEATURES,
    RandomForestMetaFilter,
)


@pytest.fixture
def synthetic_m1_df():
    """Generates synthetic M1 candles with clear trends and noise."""
    np.random.seed(42)
    n = 1500
    prices = [2000.0]
    for i in range(1, n):
        # Create alternating waves and trends
        drift = 0.3 if (i // 100) % 2 == 0 else -0.3
        shock = np.random.normal(0, 0.5)
        prices.append(prices[-1] + drift + shock)

    prices = np.array(prices)
    highs = prices + np.abs(np.random.normal(0.4, 0.1, n))
    lows = prices - np.abs(np.random.normal(0.4, 0.1, n))
    opens = prices + np.random.normal(0, 0.1, n)
    spread = np.full(n, 4.0)

    dates = pd.date_range("2026-01-01 00:00:00", periods=n, freq="1min")
    return pd.DataFrame({
        "time": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "spread": spread,
    })


def test_feature_engineering_series(synthetic_m1_df):
    feat_df = RandomForestMetaFilter.compute_technical_series(synthetic_m1_df)
    assert len(feat_df) == len(synthetic_m1_df)
    for col in ALL_CANDIDATE_FEATURES:
        assert col in feat_df.columns
        assert not feat_df[col].isna().all()


def test_meta_labeling_triple_barrier(synthetic_m1_df):
    feat_df = RandomForestMetaFilter.compute_technical_series(synthetic_m1_df)
    X, y = RandomForestMetaFilter.generate_meta_labels(feat_df, lookforward_bars=30)
    assert len(X) > 0
    assert len(X) == len(y)
    assert set(y.unique()).issubset({0, 1})
    for col in ALL_CANDIDATE_FEATURES:
        assert col in X.columns


def test_collinear_pruning():
    rf = RandomForestMetaFilter(collinear_threshold=0.85)
    # Create two synthetic features with 0.99 correlation
    np.random.seed(42)
    x1 = np.random.normal(0, 1, 200)
    x2 = x1 * 0.99 + np.random.normal(0, 0.05, 200)
    x3 = np.random.normal(5, 2, 200)

    df_test = pd.DataFrame({"feat_a": x1, "feat_b": x2, "feat_c": x3})
    pruned_df, dropped = rf.prune_collinear_features(df_test)

    assert len(dropped) == 1
    assert "feat_c" in pruned_df.columns
    # One of feat_a or feat_b should be dropped
    assert ("feat_a" in dropped and "feat_b" in pruned_df.columns) or \
           ("feat_b" in dropped and "feat_a" in pruned_df.columns)


def test_vif_pruning():
    rf = RandomForestMetaFilter(vif_threshold=5.0)
    np.random.seed(42)
    n = 300
    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)
    # Multi-collinear feature: strong linear combination of x1 and x2
    x_combo = 2.0 * x1 + 3.0 * x2 + np.random.normal(0, 0.01, n)
    x3 = np.random.normal(10, 2, n)
    x4 = np.random.normal(-5, 1, n)
    x5 = np.random.normal(1, 0.5, n)
    x6 = np.random.normal(2, 1, n)

    df_test = pd.DataFrame({
        "x1": x1,
        "x2": x2,
        "x_combo": x_combo,
        "x3": x3,
        "x4": x4,
        "x5": x5,
        "x6": x6,
    })
    pruned_df, dropped = rf.prune_vif_features(df_test, max_vif=5.0)
    assert len(dropped) >= 1
    assert "x_combo" in dropped or "x1" in dropped or "x2" in dropped
    assert len(pruned_df.columns) < len(df_test.columns)


def test_low_importance_pruning():
    rf = RandomForestMetaFilter(prune_importance_threshold=0.03, max_depth=4, min_samples_leaf=5)
    np.random.seed(42)
    n = 300
    # Strong signal
    x_signal = np.random.normal(0, 1, n)
    y = pd.Series((x_signal > 0).astype(int))

    # Pure noise feature
    x_noise = np.random.normal(0, 1, n)
    x_signal2 = x_signal + np.random.normal(0, 0.2, n)
    x_sig3 = np.random.normal(0, 1, n) * y

    df_test = pd.DataFrame({
        "sig1": x_signal,
        "sig2": x_signal2,
        "sig3": x_sig3,
        "noise1": x_noise,
        "noise2": np.random.uniform(-1, 1, n),
        "noise3": np.random.uniform(10, 20, n),
    })

    pruned_df, dropped = rf.prune_low_importance_features(df_test, y)
    assert len(pruned_df.columns) <= len(df_test.columns)
    assert len(pruned_df.columns) >= 5  # Keeps at least 5 features


def test_training_and_tree_pruning(synthetic_m1_df):
    rf = RandomForestMetaFilter(
        min_prob_threshold=0.55,
        prune_importance_threshold=0.03,
        max_depth=5,
        min_samples_leaf=15,
        min_samples_split=30,
        ccp_alpha=0.001,
        n_estimators=30,
    )
    metrics = rf.train(synthetic_m1_df, verbose=False)

    assert rf.is_fitted
    assert rf.model is not None
    assert rf.model.max_depth == 5
    assert rf.model.min_samples_leaf == 15
    assert rf.model.ccp_alpha == 0.001
    assert "filtered_win_rate" in metrics
    assert "selected_features" in metrics
    assert len(rf.selected_features) > 0


def test_trade_evaluation_and_veto(synthetic_m1_df):
    rf = RandomForestMetaFilter(
        min_prob_threshold=0.60,
        max_depth=4,
        min_samples_leaf=10,
        n_estimators=20,
    )
    rf.train(synthetic_m1_df, verbose=False)

    # State with random inputs
    test_state = {col: 0.0 for col in ALL_CANDIDATE_FEATURES}
    prob = rf.predict_probability(test_state)
    assert 0.0 <= prob <= 1.0

    approved, p, reason = rf.evaluate_trade("BUY", test_state, min_prob_override=0.999)
    # With 99.9% threshold, should be vetoed
    assert approved is False
    assert "VETO" in reason

    approved_low, p_low, reason_low = rf.evaluate_trade("BUY", test_state, min_prob_override=0.001)
    # With 0.1% threshold, should be approved
    assert approved_low is True
    assert "APPROVED" in reason_low


def test_save_and_load_persistence(synthetic_m1_df, tmp_path):
    rf = RandomForestMetaFilter(max_depth=4, min_samples_leaf=10, n_estimators=10)
    rf.train(synthetic_m1_df, verbose=False)

    save_joblib = tmp_path / "rf_filter.joblib"
    save_meta = tmp_path / "rf_meta.json"

    rf.save(save_joblib, save_meta)
    assert save_joblib.is_file()
    assert save_meta.is_file()

    loaded_rf = RandomForestMetaFilter()
    success = loaded_rf.load(save_joblib, save_meta)
    assert success is True
    assert loaded_rf.is_fitted
    assert loaded_rf.selected_features == rf.selected_features
    assert loaded_rf.model is not None
