from pydantic import BaseModel


class DashboardServicesPayload(BaseModel):
    database: str
    llm: str
    market_data: str


class DashboardRiskPayload(BaseModel):
    active_target_count: int
    open_orders: int
    broker_event_count: int
    healthy: bool
    daily_pnl: float


class DashboardAutomationPayload(BaseModel):
    today_status: str
    last_run_at: str | None
    next_run_at: str | None


class DashboardPerformancePayload(BaseModel):
    today_return: float
    month_return: float
    max_drawdown: float
    nav_curve: list[dict]
    comparison_cards: list[dict]


class DashboardHistoryPayload(BaseModel):
    auto_runs: list[dict]
    manual_runs: list[dict]
    fills: list[dict]
    decisions: list[dict]


class DashboardAlertPayload(BaseModel):
    level: str
    code: str
    message: str


class DashboardWorkbenchPayload(BaseModel):
    market: str
    account_kind: str
    services: DashboardServicesPayload
    risk: DashboardRiskPayload
    automation: DashboardAutomationPayload
    performance: DashboardPerformancePayload
    history: DashboardHistoryPayload
    alerts: list[DashboardAlertPayload]
