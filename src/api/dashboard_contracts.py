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
    window: str
    start_date: str | None
    end_date: str | None
    sample_count: int
    window_return: float
    today_return: float
    month_return: float
    max_drawdown: float
    nav_curve: list[dict]
    comparison_cards: list[dict]


class DashboardRunListItem(BaseModel):
    id: str
    source: str
    market: str
    status: str
    trade_date: str | None
    created_at: str | None
    finished_at: str | None
    decision_mode: str | None
    execution_mode: str | None
    watchlist_count: int
    decision_count: int | None
    target_count: int | None
    order_count: int | None
    net_pnl: float | None
    error_message: str | None
    run_context_id: str | None
    supports_case_view: bool


class DashboardHistoryPayload(BaseModel):
    runs: list[DashboardRunListItem]
    cursor: str | None
    has_more: bool
    next_cursor: str | None


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
