from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaAssetSnapshot:
    symbol: str
    underlying_symbol: str
    project_id: str
    market_status: str
    asset_status: str
    shares_multiplier: float
    min_qty: float | None
    max_qty: float | None
