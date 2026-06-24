"""Tests for rl/trading_env.py reward logic with costs and drawdown."""
import numpy as np
import pytest
from rl.trading_env import XAUUSDTradingEnv, ACTION_BUY, ACTION_SELL, ACTION_HOLD, POS_FLAT, POS_LONG, POS_SHORT


class TestTradingEnvReward:
    """Test suite for the reward function matching R = ΔEquity − α·Drawdown − β·TxCosts."""

    @pytest.fixture
    def env(self):
        """Create a minimal env for testing."""
        # Use synthetic data to ensure deterministic test
        return XAUUSDTradingEnv(
            csv_path=None,
            episode_length=100,
            spread_points=2.0,
            commission_per_lot=0.5,
            drawdown_penalty_alpha=0.5,
        )

    def test_entry_cost_deducted(self, env):
        """Verify that entry cost is deducted from reward on BUY."""
        env.reset()
        # Step once to get past warmup
        for _ in range(10):
            env.step(ACTION_HOLD)

        env._position = POS_FLAT
        env._equity = 0.0
        env._peak_equity = 0.0

        # Execute BUY
        reward = env.step(ACTION_BUY)[1]
        assert env._equity == -2.5, f"Expected equity -2.5 after entry cost, got {env._equity}"

    def test_exit_cost_deducted(self, env):
        """Verify that exit cost is deducted on closing."""
        env.reset()
        # Setup: already in LONG position
        env._position = POS_LONG
        env._entry_price = 1800.0
        env._equity = 0.0
        env._peak_equity = 0.0

        # Move price up and close
        env._closes[env._start_idx + env._step_idx] = 1810.0  # 10 points profit
        reward = env.step(ACTION_SELL)[1]
        # PnL = 10, cost = 2.5, net = 7.5
        assert reward > 0, "Expected positive reward on profitable close"

    def test_drawdown_penalty_applied(self, env):
        """Verify drawdown penalty is applied."""
        env.reset()
        env._position = POS_FLAT
        env._equity = 10.0
        env._peak_equity = 20.0  # peak was higher
        env._drawdown_alpha = 0.5

        # Hold should trigger drawdown penalty
        reward = env.step(ACTION_HOLD)[1]
        # equity still 10, peak 20, drawdown = 10, penalty = 0.5 * 10 = 5
        assert reward <= -5.0, f"Expected drawdown penalty ~5, got {reward}"

    def test_invalid_action_penalty(self, env):
        """Verify -2.0 penalty for invalid action."""
        env.reset()
        env._position = POS_LONG
        reward = env.step(ACTION_BUY)[1]  # Already long, BUY is invalid
        assert reward == -2.0, f"Expected -2.0 for invalid action, got {reward}"

    def test_holding_penalty(self, env):
        """Verify -0.1 holding penalty per step."""
        env.reset()
        env._position = POS_LONG
        env._equity = 0.0
        env._peak_equity = 0.0
        reward = env.step(ACTION_HOLD)[1]
        assert reward == -0.1, f"Expected -0.1 holding penalty, got {reward}"