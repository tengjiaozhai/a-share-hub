from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.market_calendar.exceptions import UnsupportedMarketError
from src.market_calendar.service import TradingCalendarService


def test_get_session_returns_trading_day_for_regular_a_share_day():
    calendar = TradingCalendarService()

    session = calendar.get_session("a", date(2026, 6, 18))

    assert session.is_trading_day is True
    assert session.open_at is not None
    assert session.close_at is not None
    assert session.open_at.tzinfo == ZoneInfo("Asia/Shanghai")


def test_get_session_skips_weekend():
    calendar = TradingCalendarService()

    session = calendar.get_session("a", date(2026, 6, 20))

    assert session.is_trading_day is False
    assert session.reason == "weekend market closure"


def test_get_session_skips_a_share_static_holiday():
    calendar = TradingCalendarService()

    session = calendar.get_session("a", date(2026, 1, 1))

    assert session.is_trading_day is False
    assert session.reason == "A股元旦休市"


def test_get_session_skips_us_static_holiday():
    calendar = TradingCalendarService()

    session = calendar.get_session("us", date(2026, 1, 1))

    assert session.is_trading_day is False
    assert session.reason == "US market New Year's Day closure"


def test_previous_and_next_trading_day_skip_weekend():
    calendar = TradingCalendarService()

    assert calendar.previous_trading_day("a", date(2026, 6, 22)) == date(2026, 6, 18)
    assert calendar.next_trading_day("a", date(2026, 6, 19)) == date(2026, 6, 22)


def test_recent_trading_days_are_ascending_and_skip_non_trading_days():
    calendar = TradingCalendarService()

    days = calendar.recent_trading_days("a", date(2026, 6, 22), count=3)

    assert days == [date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 22)]


def test_next_trading_run_at_skips_non_trading_days():
    calendar = TradingCalendarService()

    run_at = calendar.next_trading_run_at("a", datetime(2026, 6, 19, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert run_at == datetime(2026, 6, 22, 9, 15, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_unsupported_market_fails_fast():
    calendar = TradingCalendarService()

    with pytest.raises(UnsupportedMarketError):
        calendar.get_session("crypto", date(2026, 6, 18))
