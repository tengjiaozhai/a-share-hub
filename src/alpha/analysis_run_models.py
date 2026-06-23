from typing import Literal, Optional
from pydantic import BaseModel, Field


MarketTag = Literal["a", "us"]
RunStatus = Literal["accepted", "running", "completed", "failed"]
StageName = Literal["accepted", "snapshot", "research", "trader", "risk", "backtest", "completed", "failed"]
StageStatus = Literal["started", "done", "failed"]


class AnalysisRunCreateRequest(BaseModel):
    symbol: str = Field(min_length=1)
    backtest_window: str = Field(default="60d")
    include_backtest: bool = Field(default=True)


class AnalysisRunCreatedResponse(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    stream_url: str
    created_at: str


class AnalysisStageUpdate(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    stage: StageName
    status: StageStatus
    message: str = ""
    snapshot: Optional[dict] = None
    research: Optional[dict] = None
    trader: Optional[dict] = None
    risk: Optional[dict] = None
    backtest: Optional[dict] = None
    error: Optional[str] = None
    error_stage: Optional[StageName] = None
    seq: int


class AnalysisRunSummary(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    current_stage: StageName
    risk_action: Optional[str] = None
    research_rating: Optional[str] = None
    research_confidence: Optional[float] = None
    close_date: Optional[str] = None
    created_at: str
    finished_at: Optional[str] = None


class AnalysisRunDetail(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    current_stage: StageName
    model_name: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    snapshot: Optional[dict] = None
    research: Optional[dict] = None
    trader: Optional[dict] = None
    risk: Optional[dict] = None
    backtest: Optional[dict] = None
    error: Optional[str] = None
    error_stage: Optional[StageName] = None