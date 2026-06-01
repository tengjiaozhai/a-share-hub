from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaExecutionCapability:
    mode: str
    enabled: bool
    reason: str


@dataclass(frozen=True)
class AlphaExecutionRequest:
    ticket_id: str
    asset_symbol: str
    action: str
    quantity: float
    limit_price: float
