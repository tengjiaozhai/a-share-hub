from datetime import datetime

from pydantic import BaseModel


class AStockWatchlistItem(BaseModel):
    id: int = 0
    symbol: str
    name: str
    sort_order: int = 0
    created_at: datetime | None = None


class AStockKline(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AStockFundamental(BaseModel):
    symbol: str
    name: str = ""
    pe_ratio: float = 0.0
    turnover: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    market_cap: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0