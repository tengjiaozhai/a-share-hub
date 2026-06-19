from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class MarketSession:
    """A single market session for a trade date."""

    market: str
    trade_date: date
    is_trading_day: bool
    open_at: datetime | None = None
    close_at: datetime | None = None
    is_early_close: bool = False
    reason: str | None = None
