from datetime import datetime

from pydantic import BaseModel


class USQuote(BaseModel):
    symbol: str
    name: str
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0
    market_cap: int = 0
    prev_close: float = 0.0
    market_open: bool = False
    stale: bool = False
    updated_at: datetime | None = None


class USKline(BaseModel):
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime


class USFundamental(BaseModel):
    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: int = 0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    dividend_yield: float = 0.0
    eps: float = 0.0
    beta: float = 0.0
    fifty_two_week_high: float = 0.0
    fifty_two_week_low: float = 0.0


class USWatchlistItem(BaseModel):
    id: int = 0
    symbol: str
    name: str
    sort_order: int = 0
    created_at: datetime | None = None


class USBinanceAsset(BaseModel):
    symbol: str
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    usdt_value: float = 0.0
