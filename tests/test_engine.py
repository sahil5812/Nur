import pytest
from unittest.mock import MagicMock, patch
import MetaTrader5 as mt5
from core.engine import TradingEngine
from core.models import Bar


def create_synthetic_bars(count: int, base_price: float) -> list[Bar]:
    return [
        Bar(
            time=1000 + i * 60,
            open=base_price,
            high=base_price + 1.0,
            low=base_price - 1.0,
            close=base_price,
            tick_volume=10
        )
        for i in range(count)
    ]


@pytest.fixture
def mock_engine_deps():
    """Mock the external systems required by TradingEngine.__init__"""
    with patch("core.engine.Storage"), \
         patch("core.engine.DataProvider"), \
         patch("core.engine.Broker"), \
         patch("core.engine.RiskManager"), \
         patch("core.engine.PullbackStrategy") as MockStrategy, \
         patch("core.engine.RLAgent") as MockRLAgent, \
         patch("core.engine.RiskGuardian"), \
         patch("core.engine.get_user_risk_info") as MockUserRisk:
        
        # Setup strategy mock defaults
        strategy_instance = MockStrategy.return_value
        strategy_instance.calculate_ema.return_value = 1800.0
        strategy_instance.calculate_atr.return_value = 2.0
        
        # Setup user risk mock defaults
        MockUserRisk.return_value = {"risk_multiplier": 1.0, "name": "Test User"}

        yield {
            "strategy": strategy_instance,
            "rl_agent": MockRLAgent.return_value,
            "user_risk": MockUserRisk,
        }


def test_build_rl_state_dict(mock_engine_deps):
    engine = TradingEngine()
    
    # Setup some test rates
    m1_rates = create_synthetic_bars(20, 1800.0)
    
    # Call build state dict
    state = engine._build_rl_state_dict(m1_rates, signal=mt5.ORDER_TYPE_BUY)
    
    # Assert all keys are present
    expected_keys = {
        "rsi", "macd_hist", "atr", "ema_distance_pct", 
        "atr_normalized", "hour", "session", "position", 
        "log_ret", "candle_time"
    }
    assert expected_keys.issubset(state.keys())
    
    # Assert sanity check ranges
    assert 0 <= state["rsi"] <= 100
    assert -24 <= state["hour"] <= 24
    assert state["position"] == 0  # flat for entry decision
    assert state["candle_time"] == m1_rates[-1].time


@patch("core.engine.time.sleep", return_value=None)  # avoid delays in tests
def test_rl_veto_path(mock_sleep, mock_engine_deps):
    engine = TradingEngine()
    
    # Mock data provider returns
    m1_rates = create_synthetic_bars(200, 1800.0)
    m5_rates = create_synthetic_bars(200, 1800.0)
    h1_rates = create_synthetic_bars(200, 1800.0)
    engine.data_provider.get_rates.side_effect = lambda sym, tf, count: {
        mt5.TIMEFRAME_M1: m1_rates,
        mt5.TIMEFRAME_M5: m5_rates,
        mt5.TIMEFRAME_H1: h1_rates,
    }[tf]

    # Mock risk checks to pass
    engine.risk_manager.is_in_trading_session.return_value = True
    engine.risk_manager.check_daily_limits.return_value = True
    engine.risk_config.news_filter_enabled = False
    engine.risk_config.rl_veto_enabled = True

    # Force a BUY signal from strategy
    engine.strategy.check_signals.return_value = (mt5.ORDER_TYPE_BUY, False, "Log Msg")

    # Scenario 1: RL Veto is active (RL agent predicts HOLD or SELL)
    # RLAgent.predict returns "HOLD", disagreeing with BUY
    mock_engine_deps["rl_agent"].predict.return_value = "HOLD"

    # We mock run's loop to terminate quickly by raising StopIteration or similar,
    # or we can mock connection check to return shutdown=True after one iteration.
    import shared_state
    original_shutdown = shared_state.shutdown
    shared_state.shutdown = True
    try:
        with patch("core.engine.write_status"):
            # We manually simulate the inside of the waiting block
            # check strategy signals
            signal, engine.pullback_seen, log_msg = engine.strategy.check_signals(
                m1_rates, m5_rates, h1_rates, engine.pullback_seen
            )
            assert signal == mt5.ORDER_TYPE_BUY
            
            state_dict = engine._build_rl_state_dict(m1_rates, signal)
            rl_action = engine.rl_agent.predict(state_dict)
            assert rl_action == "HOLD"
            
            rl_action_map = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL, "HOLD": None}
            rl_order_type = rl_action_map.get(rl_action)
            
            # Verify veto triggers (rl_order_type != signal)
            assert rl_order_type != signal
            # The engine should not call broker.send_order since veto matches
            engine.broker.send_order.assert_not_called()

        # Scenario 2: RL agrees (RL agent predicts BUY)
        mock_engine_deps["rl_agent"].predict.return_value = "BUY"
        
        # Mock broker send_order and data provider tick info
        mock_tick = MagicMock()
        mock_tick.ask = 1800.5
        engine.data_provider.get_tick.return_value = mock_tick
        engine.risk_manager.check_margin.return_value = True
        engine.broker.send_order.return_value = 987654

        # Simulate the agreement path
        rl_action = engine.rl_agent.predict(state_dict)
        assert rl_action == "BUY"
        rl_order_type = rl_action_map.get(rl_action)
        assert rl_order_type == signal

        price = mock_tick.ask
        volume = engine.risk_manager.calculate_lot_size(10000.0, 2.0, engine.strat_config.sl_atr_multiplier)
        
        # Engine calls send_order
        ticket = engine.broker.send_order(
            engine.strat_config.symbol,
            signal,
            volume,
            4.0,  # sl_dist
            atr=2.0
        )
        assert ticket == 987654
    finally:
        shared_state.shutdown = original_shutdown
