import pytest
from datetime import datetime
from src.core.market_clock import is_continuous_session, is_am_session, is_pm_session

class TestMarketClock:
    def test_is_continuous_session_morning(self):
        """测试上午交易时段"""
        ts = datetime(2026, 5, 23, 10, 0)
        assert is_continuous_session(ts) is True

    def test_is_continuous_session_afternoon(self):
        """测试下午交易时段"""
        ts = datetime(2026, 5, 23, 14, 0)
        assert is_continuous_session(ts) is True

    def test_is_continuous_session_lunch_break(self):
        """测试午休时段"""
        ts = datetime(2026, 5, 23, 12, 0)
        assert is_continuous_session(ts) is False

    def test_is_continuous_session_before_open(self):
        """测试开盘前"""
        ts = datetime(2026, 5, 23, 9, 0)
        assert is_continuous_session(ts) is False

    def test_is_continuous_session_after_close(self):
        """测试收盘后"""
        ts = datetime(2026, 5, 23, 16, 0)
        assert is_continuous_session(ts) is False

    def test_is_am_session(self):
        """测试上午时段判断"""
        ts = datetime(2026, 5, 23, 10, 30)
        assert is_am_session(ts) is True

    def test_is_am_session_boundary(self):
        """测试上午时段边界"""
        ts = datetime(2026, 5, 23, 11, 30)
        assert is_am_session(ts) is True

    def test_is_pm_session(self):
        """测试下午时段判断"""
        ts = datetime(2026, 5, 23, 14, 30)
        assert is_pm_session(ts) is True

    def test_is_pm_session_boundary(self):
        """测试下午时段边界"""
        ts = datetime(2026, 5, 23, 15, 0)
        assert is_pm_session(ts) is True
