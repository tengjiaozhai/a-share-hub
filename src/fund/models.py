from datetime import datetime

from pydantic import BaseModel


class FundWatchlistItem(BaseModel):
    id: int = 0
    symbol: str
    name: str
    sort_order: int = 0
    created_at: datetime | None = None
