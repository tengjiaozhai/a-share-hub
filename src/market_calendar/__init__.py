from src.market_calendar.service import TradingCalendarService

_calendar_service: TradingCalendarService | None = None


def get_trading_calendar() -> TradingCalendarService:
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = TradingCalendarService()
    return _calendar_service
