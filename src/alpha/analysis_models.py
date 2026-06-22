from typing import Literal

from pydantic import BaseModel, Field, model_validator

ResearchRating = Literal["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
TraderAction = Literal["BUY", "HOLD", "SELL"]
FinalAction = Literal["ADD", "HOLD", "REDUCE", "EXIT"]


class AnalysisSnapshot(BaseModel):
    symbol: str
    market: Literal["a", "us"]
    currency: Literal["CNY", "USD"]
    as_of: str
    quantity: float = Field(ge=0)
    weighted_avg_cost: float = Field(ge=0)
    close: float = Field(gt=0)
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_ratio: float
    position_ratio: float = Field(ge=0)
    stop_loss_ratio: float
    take_profit_ratio: float
    technical: dict
    fundamentals: dict
    news: dict
    data_quality: dict


class ResearchPlan(BaseModel):
    rating: ResearchRating
    thesis: str = Field(min_length=1)
    technical_view: str = Field(min_length=1)
    fundamental_view: str = Field(min_length=1)
    sentiment_view: str = Field(min_length=1)
    catalysts: list[str]
    risks: list[str]
    confidence: float = Field(ge=0, le=1)
    data_gaps: list[str]


class TraderProposal(BaseModel):
    action: TraderAction
    reasoning: str = Field(min_length=1)
    entry_low: float | None = Field(default=None, gt=0)
    entry_high: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    position_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.entry_low is not None and self.entry_high is not None and self.entry_low > self.entry_high:
            raise ValueError("entry_low must be <= entry_high")
        return self


class RiskDecision(BaseModel):
    action: FinalAction
    reason: str = Field(min_length=1)
    triggered_rules: list[str]
    approved_position_ratio: float = Field(ge=0, le=1)


class AnalysisRunResult(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    snapshot: AnalysisSnapshot | None
    research: ResearchPlan | None
    trader: TraderProposal | None
    risk: RiskDecision | None
    model_name: str
    error: str | None
    created_at: str
