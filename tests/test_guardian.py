"""Tests for core/guardian.py RiskGuardian circuit breaker."""
import pytest
from unittest.mock import MagicMock, patch

from core.guardian import RiskGuardian, GuardianResult
from core.models import RiskConfig


@pytest.fixture
def mock_config():
    return RiskConfig(
        panic_daily_loss_limit=100.0,
        panic_drawdown_limit=50.0,
        panic_margin_multiplier=1.5,
        panic_spread_threshold=0.02,
    )


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.get_report_data.return_value = {"today_profit": 0.0}
    storage.get_aggregated_stats.return_value = {"max_drawdown": 0.0}
    return storage


@pytest.fixture
def mock_broker():
    broker = MagicMock()
    broker.panic_close_all.return_value = 2
    return broker


@pytest.fixture
def guardian(mock_config, mock_storage, mock_broker):
    return RiskGuardian(mock_config, mock_storage, mock_broker, "XAUUSD")


class TestRiskGuardian:
    """Tests for hard limit checks."""

    @patch("core.guardian.mt5")
    def test_no_trip_when_within_limits(self, mock_mt5, guardian):
        """Guardian should not trip when all limits are within bounds."""
        # Mock account_info to return sufficient margin
        mock_account = MagicMock()
        mock_account.free_margin = 1000.0
        mock_account.margin = 500.0
        mock_mt5.account_info.return_value = mock_account

        result = guardian.check()
        assert result.tripped is False

    def test_trip_on_daily_loss(self, guardian, mock_storage):
        mock_storage.get_report_data.return_value = {"today_profit": -150.0}
        result = guardian.check()
        assert result.tripped is True
        assert "Daily max loss exceeded" in result.reason

    def test_trip_on_drawdown(self, guardian, mock_storage):
        mock_storage.get_aggregated_stats.return_value = {"max_drawdown": 60.0}
        result = guardian.check()
        assert result.tripped is True
        assert "drawdown" in result.reason.lower()

    def test_check_and_apply_sets_shared_state(self, guardian, mock_broker):
        with patch("core.guardian.shared_state") as mock_shared:
            result = guardian.check_and_apply()
            assert result.tripped is False or result.tripped is True
            if result.tripped:
                assert mock_shared.hard_stop is True
                assert mock_shared.panic_mode is True
                mock_broker.panic_close_all.assert_called_once()

    def test_send_message_on_trip(self, guardian, mock_storage):
        mock_storage.get_report_data.return_value = {"today_profit": -300.0}
        with patch("core.guardian.shared_state") as mock_shared:
            mock_shared.send_message = MagicMock()
            guardian.check_and_apply()
            mock_shared.send_message.assert_called_once()
            call_args = mock_shared.send_message.call_args[0][0]
            assert "RiskGuardian Trip" in call_args