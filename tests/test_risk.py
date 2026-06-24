import pytest
from unittest.mock import MagicMock, patch
from core.risk import RiskManager
from core.models import RiskConfig


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.get_report_data.return_value = {"today_profit": 0.0}
    storage.get_aggregated_stats.return_value = {"max_drawdown": 0.0}
    
    # Mocking SQLite lock and connection for trade counting
    storage.lock = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_conn.cursor.return_value = mock_cursor
    storage._get_connection.return_value = mock_conn
    return storage


@pytest.fixture
def risk_config():
    return RiskConfig(
        risk_percent=1.0,
        max_daily_loss=500.0,
        max_trades_per_day=5,
        max_drawdown_limit=1000.0,
        london_start="08:00",
        london_end="16:00",
        ny_start="13:00",
        ny_end="21:00",
        timezone_offset="+00:00",
        news_filter_enabled=True,
    )


@pytest.fixture
def risk_manager(risk_config, mock_storage):
    return RiskManager(risk_config, mock_storage)


class TestRiskManager:
    def test_calculate_lot_size(self, risk_manager):
        # Normal calculation:
        # risk_amount = 10000 * 1% = 100
        # sl_distance = atr (2.0) * sl_atr_multiplier (1.5) = 3.0
        # lot = 100 / (3.0 * 100) = 0.33
        lot = risk_manager.calculate_lot_size(balance=10000.0, atr=2.0, sl_atr_multiplier=1.5)
        assert lot == 0.33

        # Guard calculation: SL distance <= 0
        lot_zero = risk_manager.calculate_lot_size(balance=10000.0, atr=0.0, sl_atr_multiplier=1.5)
        assert lot_zero == 0.01

        lot_neg = risk_manager.calculate_lot_size(balance=10000.0, atr=-1.0, sl_atr_multiplier=1.5)
        assert lot_neg == 0.01

    @patch("core.risk.shared_state")
    def test_check_daily_limits_flags(self, mock_shared, risk_manager):
        # If panic_mode is active
        mock_shared.panic_mode = True
        mock_shared.hard_stop = False
        mock_shared.soft_stop = False
        assert risk_manager.check_daily_limits() is False

        # If hard_stop is active
        mock_shared.panic_mode = False
        mock_shared.hard_stop = True
        assert risk_manager.check_daily_limits() is False

        # If soft_stop is active
        mock_shared.hard_stop = False
        mock_shared.soft_stop = True
        assert risk_manager.check_daily_limits() is False

    @patch("core.risk.shared_state")
    def test_check_daily_limits_loss_limit(self, mock_shared, risk_manager, mock_storage):
        mock_shared.panic_mode = False
        mock_shared.hard_stop = False
        mock_shared.soft_stop = False

        # Exceed daily loss: max_daily_loss is 500.0, profit = -600.0
        mock_storage.get_report_data.return_value = {"today_profit": -600.0}
        assert risk_manager.check_daily_limits() is False
        assert mock_shared.soft_stop is True

    @patch("core.risk.shared_state")
    def test_check_daily_limits_drawdown(self, mock_shared, risk_manager, mock_storage):
        mock_shared.panic_mode = False
        mock_shared.hard_stop = False
        mock_shared.soft_stop = False

        # Exceed max drawdown: max_drawdown_limit is 1000.0, max_drawdown = 1200.0
        mock_storage.get_aggregated_stats.return_value = {"max_drawdown": 1200.0}
        assert risk_manager.check_daily_limits() is False
        assert mock_shared.soft_stop is True

    @patch("core.risk.shared_state")
    def test_check_daily_limits_trade_count(self, mock_shared, risk_manager, mock_storage):
        mock_shared.panic_mode = False
        mock_shared.hard_stop = False
        mock_shared.soft_stop = False

        # Exceed daily trade count: limit is 5, today trades = 6
        mock_cursor = mock_storage._get_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (6,)
        
        assert risk_manager.check_daily_limits() is False

    @patch("core.risk.mt5")
    def test_check_margin(self, mock_mt5, risk_manager):
        # Setup mock account and check_result
        mock_account = MagicMock()
        mock_account.free_margin = 1000.0
        mock_mt5.account_info.return_value = mock_account

        mock_check_result = MagicMock()
        mock_check_result.retcode = 0
        mock_check_result.margin = 500.0  # margin needed
        mock_mt5.order_check.return_value = mock_check_result

        # free_margin = 1000, required_margin = 500 * 1.1 = 550 (Sufficient)
        assert risk_manager.check_margin("XAUUSD", 0, 1.0, 1800.0) is True

        # free_margin = 500, required_margin = 500 * 1.1 = 550 (Insufficient)
        mock_account.free_margin = 500.0
        assert risk_manager.check_margin("XAUUSD", 0, 1.0, 1800.0) is False

        # Check result failure
        mock_check_result.retcode = 10014
        assert risk_manager.check_margin("XAUUSD", 0, 1.0, 1800.0) is False
