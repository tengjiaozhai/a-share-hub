from typing import Literal
from pydantic import BaseModel, Field

class DecisionOutput(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD", "WATCH"]
    confidence: int = Field(ge=0, le=100)
    target_position_ratio: float = Field(ge=0.0, le=1.0)
    reason: str
