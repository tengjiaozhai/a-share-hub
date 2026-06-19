from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.market_calendar.exceptions import UnsupportedMarketError
from src.market_calendar.models import MarketSession
from src.market_calendar.static_calendars import (
    CN_TZ,
    DAILY_RUN_TIMES_CN,
    MARKET_HOLIDAYS,
    MARKET_SESSIONS,
    MARKET_TIMEZONES,
)

MAX_CALENDAR_LOOKUP_DAYS = 370


class TradingCalendarService:
    """Trading calendar service used by scheduler, backfill, and dashboard."""

    def get_session(self, market: str, trade_date: date) -> MarketSession:
        self._validate_market(market)

        if trade_date.weekday() >= 5:
            return MarketSession(
                market=market,
                trade_date=trade_date,
                is_trading_day=False,
                reason="weekend market closure",
            )

        holiday_reason = MARKET_HOLIDAYS[market].get(trade_date.isoformat())
        if holiday_reason:
            return MarketSession(
                market=market,
                trade_date=trade_date,
                is_trading_day=False,
                reason=holiday_reason,
            )

        market_tz = MARKET_TIMEZONES[market]
        open_time, close_time = MARKET_SESSIONS[market]
        return MarketSession(
            market=market,
            trade_date=trade_date,
            is_trading_day=True,
            open_at=datetime.combine(trade_date, open_time, tzinfo=market_tz),
            close_at=datetime.combine(trade_date, close_time, tzinfo=market_tz),
        )

    def is_trading_day(self, market: str, trade_date: date) -> bool:
        return self.get_session(market, trade_date).is_trading_day

    def previous_trading_day(self, market: str, trade_date: date) -> date:
        cursor = trade_date - timedelta(days=1)
        for _ in range(MAX_CALENDAR_LOOKUP_DAYS):
            if self.is_trading_day(market, cursor):
                return cursor
            cursor -= timedelta(days=1)
        raise RuntimeError(f"unable to resolve previous trading day for {market} before {trade_date}")

    def next_trading_day(self, market: str, trade_date: date) -> date:
        cursor = trade_date + timedelta(days=1)
        for _ in range(MAX_CALENDAR_LOOKUP_DAYS):
            if self.is_trading_day(market, cursor):
                return cursor
            cursor += timedelta(days=1)
        raise RuntimeError(f"unable to resolve next trading day for {market} after {trade_date}")

    def recent_trading_days(self, market: str, end_date: date, count: int) -> list[date]:
        if count <= 0:
            return []

        result: list[date] = []
        cursor = end_date
        for _ in range(MAX_CALENDAR_LOOKUP_DAYS):
            if self.is_trading_day(market, cursor):
                result.append(cursor)
                if len(result) == count:
                    return list(reversed(result))
            cursor -= timedelta(days=1)
        raise RuntimeError(f"unable to resolve {count} recent trading days for {market} ending {end_date}")

    def should_run_daily_job(self, market: str, now: datetime) -> tuple[bool, str | None]:
        trade_date = now.astimezone(CN_TZ).date()
        session = self.get_session(market, trade_date)
        return session.is_trading_day, session.reason

    def next_trading_run_at(self, market: str, after: datetime | None = None) -> datetime:
        self._validate_market(market)
        now = after.astimezone(CN_TZ) if after else datetime.now(CN_TZ)
        run_time = DAILY_RUN_TIMES_CN[market]
        today_run_at = datetime.combine(now.date(), run_time, tzinfo=CN_TZ)

        if now <= today_run_at and self.is_trading_day(market, now.date()):
            return today_run_at

        next_day = self.next_trading_day(market, now.date())
        return datetime.combine(next_day, run_time, tzinfo=CN_TZ)

    @staticmethod
    def daily_run_time_cn(market: str) -> time:
        try:
            return DAILY_RUN_TIMES_CN[market]
        except KeyError as exc:
            raise UnsupportedMarketError(f"unsupported market: {market}") from exc

    @staticmethod
    def market_timezone(market: str) -> ZoneInfo:
        try:
            return MARKET_TIMEZONES[market]
        except KeyError as exc:
            raise UnsupportedMarketError(f"unsupported market: {market}") from exc

    @staticmethod
    def _validate_market(market: str) -> None:
        if market not in MARKET_TIMEZONES:
            raise UnsupportedMarketError(f"unsupported market: {market}")
