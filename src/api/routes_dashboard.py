import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.agents.llm_client import LLMClient
from src.alpha.execution_service import AlphaExecutionService
from src.api.dashboard_page.render import render_dashboard_html
from src.core.config import Settings
from src.core.market_rules import resolve_lot_size
from src.data.providers.akshare_provider import AkshareProvider
from src.storage.dependencies import get_runtime_store
from src.storage.runtime_store import RuntimeStore

_CST = timezone(timedelta(hours=8))


def _now_cst() -> datetime:
    """返回北京时间（CST, UTC+8）"""
    return datetime.now(_CST)


def _today_close_cst() -> datetime:
    """返回今天 A 股收盘时间（北京时间 15:00:00），若已过则推到次日"""
    today = _now_cst().replace(hour=15, minute=0, second=0, microsecond=0)
    if today <= _now_cst():
        today = today + timedelta(days=1)
    return today

_llm_client: LLMClient | None = None
_akshare: AkshareProvider | None = None
_alpha_execution_service: AlphaExecutionService | None = None


def _get_alpha_execution_service() -> AlphaExecutionService:
    global _alpha_execution_service
    if _alpha_execution_service is None:
        _alpha_execution_service = AlphaExecutionService(mode="manual", gateway=None)
    return _alpha_execution_service


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _probe_services() -> dict:
    """探测 LLM 和行情状态，返回 ok / error / unknown"""
    settings = Settings()

    # LLM 探针：有 api_key 即认为 ok，避免每次消耗 token
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        llm_status = "ok"  # mock 模式
    else:
        llm_status = "ok"  # api_key 已配置

    # 行情探针：检查 akshare 是否可导入
    if settings.market_data_provider == "mock":
        market_status = "ok"
    else:
        global _akshare
        if _akshare is None:
            _akshare = AkshareProvider()
        market_status = "ok" if _akshare.is_available() else "error"

    return {"database": "ok", "llm": llm_status, "market": market_status}

router = APIRouter()

_HISTORY_LIMIT = 100


def _build_alpha_panel_payload(store: RuntimeStore) -> dict:
    tickets = store.list_alpha_tickets()
    latest_ticket_id = tickets[0]["ticket_id"] if tickets else None
    latest_snapshot = store.get_latest_alpha_portfolio_snapshot()
    recon_runs = store.list_alpha_reconciliation_runs()
    latest_recon = recon_runs[0] if recon_runs else None
    capability = _get_alpha_execution_service().get_capability()
    capability_payload = capability if isinstance(capability, dict) else capability.__dict__
    return {
        "tickets": tickets,
        "fills": store.list_alpha_manual_fills(ticket_id=latest_ticket_id) if latest_ticket_id else [],
        "portfolio": {
            "positions": store.list_alpha_positions(),
            "snapshot": latest_snapshot,
        },
        "exceptions": {
            "latest_status": latest_recon["status"] if latest_recon else "UNKNOWN",
            "latest_discrepancies": latest_recon["discrepancies"] if latest_recon else {},
        },
        "research": {
            "watchlist": store.list_alpha_watchlist_items(),
            "latest_candidates": [],
        },
        "execution_capability": capability_payload,
    }


def _compute_order_pnl(action: str, quantity: int, fill_price: float, current_price: float) -> float:
    """根据成交价和当前市价计算模拟盈亏。"""
    if action == "BUY":
        return round((current_price - fill_price) * quantity, 2)
    else:
        return round((fill_price - current_price) * quantity, 2)


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(store: RuntimeStore = Depends(get_runtime_store)):
    prefs = store.get_preference("dashboard") or {}
    theme_id = prefs.get("theme_id", "trading-terminal")
    return render_dashboard_html(theme_id=theme_id)


@router.get("/api/v1/dashboard/workbench")
def get_workbench(
    market: str = Query(default="a", description="市场: a 或 us"),
    account_kind: str = Query(default="auto", description="账户类型: auto 或 manual"),
    run_context_id: str | None = Query(default=None),
    decisions_page: int = Query(default=1, ge=1, description="决策页码"),
    orders_page: int = Query(default=1, ge=1, description="订单页码"),
    targets_page: int = Query(default=1, ge=1, description="目标仓位页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    store: RuntimeStore = Depends(get_runtime_store),
) -> dict:
    if run_context_id:
        summary = store.get_dashboard_run_summary(run_context_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="run_context_id not found")
        return summary["latest_workbench"]
    payload = _build_workbench_payload(
        store,
        market=market,
        decisions_page=decisions_page,
        orders_page=orders_page,
        targets_page=targets_page,
        page_size=page_size,
    )
    payload["alpha"] = _build_alpha_panel_payload(store)
    return payload


def _launch_dashboard_run(run_context_id: str, config: dict) -> None:
    from src.execution.shadow_run_service import ShadowRunService

    store = get_runtime_store()
    settings = Settings()
    llm = _get_llm()
    provider = AkshareProvider()
    service = ShadowRunService(store=store, settings=settings, llm=llm, provider=provider)
    service.run(run_context_id=run_context_id, config=config)


@router.post("/api/v1/dashboard/runs", status_code=202)
def start_dashboard_run(
    config: dict | None = None,
    background_tasks: BackgroundTasks = None,
    store: RuntimeStore = Depends(get_runtime_store),
) -> dict:
    payload = config or {}
    run_context_id = f"wrk-{_now_cst().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    store.upsert_dashboard_run_summary(
        run_context_id=run_context_id,
        trade_date=_now_cst().date().isoformat(),
        decision_mode=str(payload.get("decision_mode", "mock")),
        execution_mode="decision" if payload.get("execution_mode") == "decision" else "full",
        capital_base=int(payload.get("capital_base", 1_000_000)),
        status="accepted",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at=_now_cst().isoformat(),
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": run_context_id, "steps": []}},
    )
    store.append_dashboard_run_event(
        run_context_id=run_context_id,
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "请求已提交，等待后台执行"},
    )
    background_tasks.add_task(_launch_dashboard_run, run_context_id, payload)
    return {
        "run_context_id": run_context_id,
        "stream_url": f"/api/v1/dashboard/runs/{run_context_id}/events",
        "status": "accepted",
    }


@router.get("/api/v1/dashboard/runs/{run_context_id}/events")
async def stream_dashboard_run_events(
    run_context_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    store: RuntimeStore = Depends(get_runtime_store),
) -> EventSourceResponse:
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def event_iter():
        last_seq = after_seq
        while True:
            events = store.list_dashboard_run_events(run_context_id, after_seq=last_seq)
            for event in events:
                last_seq = event["seq"]
                yield {
                    "id": str(event["seq"]),
                    "event": event["event_type"],
                    "data": json.dumps(event, ensure_ascii=True),
                }
            summary = store.get_dashboard_run_summary(run_context_id)
            if summary and summary["status"] in {"completed", "failed"}:
                return
            await asyncio.sleep(0.2)

    return EventSourceResponse(
        event_iter(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/api/v1/dashboard/performance")
def get_performance(
    market: str = Query(default="a"),
    account_kind: str = Query(default="auto"),
    window: str = Query(default="30d"),
) -> dict:
    from sqlalchemy.orm import Session as OrmSession
    from src.paper_ledger.store import PaperLedgerStore
    from src.storage.dependencies import get_runtime_store

    engine = get_runtime_store().engine
    with OrmSession(engine) as session:
        ledger = PaperLedgerStore(session)
        account = ledger.get_or_create_account(market, account_kind)

        days_map = {"7d": 7, "30d": 30, "90d": 90, "180d": 180, "365d": 365}
        days = days_map.get(window, 30)
        nav_rows = ledger.get_nav_history(account.account_id, days=days)
        history = [
            {"trade_date": row.trade_date.isoformat(), "nav": float(row.nav)}
            for row in nav_rows
        ]

        perf = _build_performance_payload(history)

        windows = ["7d", "30d", "90d", "ytd"]
        comparison = ledger.get_comparison_windows(account.account_id, windows)
        perf["comparison_cards"] = [
            {"window": w, "return": comparison.get(w, 0.0)} for w in windows
        ]

        return perf


@router.get("/api/v1/dashboard/automation")
def get_automation(
    market: str = Query(default="a"),
    account_kind: str = Query(default="auto"),
) -> dict:
    return _load_automation_state(None, market=market)


@router.get("/api/v1/dashboard/history")
def get_history(
    market: str = Query(default="a"),
    account_kind: str = Query(default="auto"),
    source: str = Query(default="all", description="auto, manual, backfill, or all"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    from sqlalchemy.orm import Session as OrmSession
    from src.paper_ledger.store import PaperLedgerStore
    from src.storage.dependencies import get_runtime_store

    engine = get_runtime_store().engine
    with OrmSession(engine) as session:
        ledger = PaperLedgerStore(session)
        runs = ledger.get_run_history(market, source=source, limit=limit)

        auto_runs = []
        manual_runs = []
        for run in runs:
            entry = {
                "run_id": run.run_id,
                "trade_date": run.trade_date.isoformat(),
                "status": run.status,
                "source": run.run_source,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            if run.run_source == "auto":
                auto_runs.append(entry)
            else:
                manual_runs.append(entry)

        account = ledger.get_or_create_account(market, account_kind)
        nav_rows = ledger.get_nav_history(account.account_id, days=limit)
        fills = [
            {
                "nav_id": row.nav_id,
                "trade_date": row.trade_date.isoformat(),
                "nav": float(row.nav),
                "source": row.source,
            }
            for row in nav_rows
        ]

        return {
            "auto_runs": auto_runs,
            "manual_runs": manual_runs,
            "fills": fills,
            "decisions": [],
        }


def _build_performance_payload(history: list[dict]) -> dict:
    """根据 nav 历史计算今日/月度收益、最大回撤、净值曲线"""
    if not history:
        return {"today_return": 0.0, "month_return": 0.0, "max_drawdown": 0.0, "nav_curve": []}

    sorted_history = sorted(history, key=lambda row: row.get("trade_date") or "")
    nav_values = [float(row.get("nav", 0.0)) for row in sorted_history]
    today_return = 0.0
    month_return = 0.0
    max_drawdown = 0.0

    if len(nav_values) >= 2:
        today_return = round((nav_values[-1] - nav_values[-2]) / nav_values[-2], 6) if nav_values[-2] else 0.0
        month_return = round((nav_values[-1] - nav_values[0]) / nav_values[0], 6) if nav_values[0] else 0.0

        peak = nav_values[0]
        for nav in nav_values:
            if nav > peak:
                peak = nav
            if peak > 0:
                drawdown = (peak - nav) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        max_drawdown = round(max_drawdown, 6)

    nav_curve = [
        {"trade_date": row.get("trade_date"), "nav": float(row.get("nav", 0.0))}
        for row in sorted_history
    ]
    return {
        "today_return": today_return,
        "month_return": month_return,
        "max_drawdown": max_drawdown,
        "nav_curve": nav_curve,
    }


def _build_automation_payload(
    last_run_at: str | None = None,
    last_status: str | None = None,
    next_run_at: str | None = None,
) -> dict:
    """构建自动交易状态卡片数据"""
    return {
        "today_status": last_status or "pending",
        "last_run_at": last_run_at,
        "next_run_at": next_run_at,
    }


def _load_paper_nav_history(store, market: str = "a") -> list[dict]:
    """从 paper_ledger 加载净值历史；如未初始化则返回空列表"""
    try:
        from sqlalchemy.orm import Session
        from src.paper_ledger.store import PaperLedgerStore
        from src.storage.dependencies import get_runtime_store

        engine = get_runtime_store().engine
        with Session(engine) as session:
            ledger = PaperLedgerStore(session)
            account = ledger.get_or_create_account(market, "auto")
            nav_rows = ledger.get_nav_history(account.account_id, days=30)
            return [
                {"trade_date": row.trade_date.isoformat(), "nav": float(row.nav)}
                for row in nav_rows
            ]
    except Exception:
        return []


def _load_automation_state(store, market: str = "a") -> dict:
    """从 paper_ledger 加载最新 auto run + 调度器下次时间"""
    last_run_at: str | None = None
    last_status: str | None = None
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from src.paper_ledger.models import PaperRunRow
        from src.storage.dependencies import get_runtime_store

        engine = get_runtime_store().engine
        with Session(engine) as session:
            stmt = (
                select(PaperRunRow)
                .where(PaperRunRow.market == market)
                .where(PaperRunRow.run_source == "auto")
                .order_by(PaperRunRow.created_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is not None:
                last_run_at = row.created_at.isoformat() if row.created_at else None
                last_status = row.status
    except Exception:
        pass

    next_run_at: str | None = None
    try:
        from src.scheduler.daily_scheduler import get_scheduler

        scheduler = get_scheduler()
        job_id = "a_share_daily" if market == "a" else "us_daily"
        for job in scheduler._scheduler.get_jobs():
            if job.id == job_id:
                next_run_at = job.next_run_time.isoformat() if job.next_run_time else None
                break
    except Exception:
        pass

    return _build_automation_payload(
        last_run_at=last_run_at,
        last_status=last_status,
        next_run_at=next_run_at,
    )


def _build_workbench_payload(store, latest_run_override: dict | None = None, market: str = "a",
                              decisions_page: int = 1, orders_page: int = 1,
                              targets_page: int = 1, page_size: int = 20) -> dict:
    reconciliation = store.get_reconciliation_status()

    # Paginated queries
    d_offset = (decisions_page - 1) * page_size
    o_offset = (orders_page - 1) * page_size
    t_offset = (targets_page - 1) * page_size

    decision_rows = store.list_decision_runs(limit=page_size, offset=d_offset)
    target_rows = store.list_active_target_positions(limit=page_size, offset=t_offset)
    order_rows = store.list_execution_orders(limit=page_size, offset=o_offset)

    decisions = [_serialize_decision_row(row) for row in decision_rows]
    targets = [_serialize_target_row(row) for row in target_rows]
    orders = [_serialize_order_row(row) for row in order_rows]
    daily_pnl = store.sum_daily_pnl()

    # Counts for pagination
    decisions_total = store.count_decision_runs()
    orders_total = store.count_execution_orders()
    targets_total = store.count_active_target_positions()

    latest_run = latest_run_override or _build_latest_run(
        decisions=decisions,
        targets=targets,
        orders=orders,
        daily_pnl=daily_pnl,
    )

    return {
        "mode": "shadow",
        "trade_date": _now_cst().date().isoformat(),
        "last_run_at": latest_run.get("finished_at") or latest_run.get("started_at"),
        "services": _probe_services(),
        "kill_switch": {"active": store.get_kill_switch()},
        "performance": _build_performance_payload(_load_paper_nav_history(store, market)),
        "automation": _load_automation_state(store, market),
        "risk": {
            "active_target_count": len(targets),
            "open_orders": reconciliation.get("open_orders", 0),
            "broker_event_count": reconciliation.get("broker_event_count", 0),
            "healthy": reconciliation.get("healthy", False),
            "daily_pnl": daily_pnl,
        },
        "latest_run": latest_run,
        "history": {
            "decisions": decisions,
            "orders": orders,
            "targets": targets,
            "events": _list_recent_events(store, limit=page_size),
        },
        "pagination": {
            "decisions": {"page": decisions_page, "page_size": page_size, "total": decisions_total, "total_pages": max(1, -(-decisions_total // page_size))},
            "orders": {"page": orders_page, "page_size": page_size, "total": orders_total, "total_pages": max(1, -(-orders_total // page_size))},
            "targets": {"page": targets_page, "page_size": page_size, "total": targets_total, "total_pages": max(1, -(-targets_total // page_size))},
        },
    }


def _build_latest_run(decisions: list[dict], targets: list[dict], orders: list[dict], daily_pnl: float) -> dict:
    if not decisions and not targets and not orders:
        return {"status": "idle", "steps": []}

    latest_prompt_hash = decisions[0].get("prompt_hash")
    latest_decision_mode = (
        (((decisions[0].get("input_snapshot") or {}).get("features") or {}).get("decision_mode"))
        or "mock"
    )
    if latest_prompt_hash:
        run_decisions = [row for row in decisions if row.get("prompt_hash") == latest_prompt_hash]
    else:
        run_decisions = decisions[:1]
    run_decisions = sorted(run_decisions, key=lambda row: row.get("created_at") or "")

    run_decision_ids = {row.get("decision_run_id") for row in run_decisions}
    run_targets = [row for row in targets if row.get("decision_run_id") in run_decision_ids]
    run_targets = sorted(run_targets, key=lambda row: row.get("created_at") or "")
    run_target_ids = {row.get("target_position_id") for row in run_targets}
    run_orders = [row for row in orders if row.get("target_position_id") in run_target_ids]
    run_orders = sorted(run_orders, key=lambda row: row.get("created_at") or "")

    decision_items = [
        {
            "symbol": row.get("symbol"),
            "action": row.get("action"),
            "confidence": row.get("confidence"),
            "reason": row.get("reason"),
        }
        for row in run_decisions[:5]
    ]
    target_items = [
        {
            "symbol": row.get("symbol"),
            "target_quantity": _derive_target_quantity(row.get("target_value"), row.get("action")),
            "target_position_ratio": row.get("target_position_ratio"),
            "action": row.get("action"),
        }
        for row in run_targets[:5]
    ]
    order_items = [
        {
            "symbol": row.get("symbol"),
            "action": row.get("action"),
            "quantity": row.get("quantity"),
            "limit_price": row.get("limit_price"),
            "fill_price": row.get("fill_price"),
            "fee": row.get("fee"),
            "pnl_delta": row.get("pnl_delta"),
            "status": row.get("status"),
        }
        for row in run_orders[:5]
    ]
    decision_only = len(order_items) == 0
    run_context_id = _extract_run_context_id(latest_prompt_hash) or run_decisions[0].get("decision_run_id")

    latest_run = _build_run_timeline(
        run_context_id=run_context_id,
        watchlist=[row.get("symbol") for row in run_decisions if row.get("symbol")],
        capital_base=1_000_000,
        decision_mode=latest_decision_mode,
        decision_items=decision_items,
        target_items=target_items,
        order_items=order_items,
        decision_only=decision_only,
        daily_pnl=daily_pnl,
    )

    started_candidates = [
        row.get("created_at")
        for row in [*(run_decisions[:1]), *(run_targets[:1]), *(run_orders[:1])]
        if row.get("created_at")
    ]
    if started_candidates:
        latest_run["started_at"] = min(started_candidates)
        latest_run["finished_at"] = max(started_candidates)
    return latest_run


def _serialize_decision_row(row: dict) -> dict:
    parsed_action = row.get("parsed_action")
    return {
        "decision_run_id": row.get("decision_run_id"),
        "prompt_hash": row.get("prompt_hash"),
        "symbol": row.get("symbol"),
        "parsed_action": parsed_action,
        "action": _map_action(parsed_action),
        "confidence": row.get("confidence"),
        "reason": row.get("reason", ""),
        "input_snapshot": row.get("input_snapshot", {}),
        "created_at": row.get("created_at"),
    }


def _serialize_target_row(row: dict) -> dict:
    return {
        "target_position_id": row.get("target_position_id"),
        "decision_run_id": row.get("decision_run_id"),
        "symbol": row.get("symbol"),
        "action": row.get("action"),
        "target_value": row.get("target_value"),
        "target_quantity": _derive_target_quantity(row.get("target_value"), row.get("action")),
        "target_position_ratio": row.get("target_position_ratio"),
        "status": row.get("status"),
        "expires_at": row.get("expires_at"),
        "created_at": row.get("created_at"),
    }


def _serialize_order_row(row: dict) -> dict:
    return {
        "execution_order_id": row.get("execution_order_id"),
        "target_position_id": row.get("target_position_id"),
        "symbol": row.get("symbol"),
        "action": row.get("action"),
        "quantity": row.get("quantity"),
        "limit_price": row.get("limit_price"),
        "fill_price": row.get("fill_price"),
        "fee": row.get("fee"),
        "pnl_delta": row.get("pnl_delta"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }


def _map_action(parsed_action: str | None) -> str:
    if not parsed_action:
        return "HOLD"
    normalized = str(parsed_action).upper()
    if normalized in {"BUY", "SELL", "HOLD"}:
        return normalized
    if normalized in {"NONE", "NO_ACTION", "WAIT"}:
        return "HOLD"
    return normalized


def _list_recent_events(store, limit: int) -> list[dict]:
    kill_switch_events = store.list_kill_switch_events(limit=limit)
    broker_events = store.list_broker_events(limit=limit)

    events: list[dict] = []
    for row in kill_switch_events:
        events.append(
            {
                "type": "kill_switch_event",
                "kill_switch_event_id": row.get("kill_switch_event_id"),
                "active": row.get("active"),
                "reason": row.get("reason"),
                "created_at": row.get("created_at"),
            }
        )
    for row in broker_events:
        events.append(
            {
                "type": "broker_event",
                "event_id": row.get("event_id"),
                "order_id": row.get("order_id"),
                "event_type": row.get("event_type"),
                "payload": row.get("payload"),
                "created_at": row.get("created_at"),
            }
        )

    return sorted(events, key=lambda item: item.get("created_at") or "", reverse=True)[:limit]


def _extract_run_context_id(prompt_hash: str | None) -> str | None:
    if not prompt_hash:
        return None
    prefix = "dashboard-"
    return prompt_hash[len(prefix):] if prompt_hash.startswith(prefix) else prompt_hash


def _derive_target_quantity(target_value: int | None, action: str | None) -> int | str:
    if action == "SELL":
        return "0 (清仓)"
    if not target_value:
        return 0
    return int(target_value // 1000)


def _allocate_pnl_deltas(total_pnl: float, item_count: int) -> list[float]:
    if item_count <= 0:
        return []
    total_cents = int(round(total_pnl * 100))
    base = total_cents // item_count
    remainder = total_cents % item_count
    cents = [base + (1 if idx < remainder else 0) for idx in range(item_count)]
    return [round(value / 100.0, 2) for value in cents]


def _format_pnl_label(daily_pnl: float) -> str:
    sign = "+" if daily_pnl >= 0 else "-"
    amount = abs(daily_pnl)
    return f"{sign}¥{amount:,.0f}"


def _build_empty_execution_messages(decision_items: list[dict], target_items: list[dict]) -> dict[str, str]:
    if target_items:
        return {}

    buy_decisions = [row for row in decision_items if row.get("action") == "BUY"]
    sell_decisions = [row for row in decision_items if row.get("action") == "SELL"]

    if buy_decisions:
        return {
            "target": "资金不足或最小交易单位限制，未生成可执行订单",
            "execute": "无可执行订单，已跳过模拟执行",
            "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
        }
    if sell_decisions:
        return {
            "target": "当前无可卖持仓，未生成可执行订单",
            "execute": "无可执行订单，已跳过模拟执行",
            "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
        }
    return {
        "target": "本轮无买卖信号，未生成目标仓位",
        "execute": "无可执行订单，已跳过模拟执行",
        "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
    }


def _build_run_timeline(
    run_context_id: str | None,
    watchlist: list[str],
    capital_base: int,
    decision_mode: str,
    decision_items: list[dict],
    target_items: list[dict],
    order_items: list[dict],
    decision_only: bool,
    daily_pnl: float,
) -> dict:
    now = _now_cst().isoformat()
    empty_messages = _build_empty_execution_messages(decision_items, target_items)

    target_done_step = {
        "stage": "target",
        "status": "done",
        "timestamp": now,
        "items": target_items,
    } if target_items else {
        "stage": "target",
        "status": "done",
        "timestamp": now,
        "message": empty_messages["target"],
    }

    steps = [
        {
            "stage": "decision",
            "status": "running",
            "timestamp": now,
            "message": f"输入标的: {', '.join(watchlist)} | 资金: ¥{capital_base:,} | 模式: {decision_mode}",
        },
        {
            "stage": "decision",
            "status": "done",
            "timestamp": now,
            "items": decision_items,
        },
        {
            "stage": "target",
            "status": "running",
            "timestamp": now,
            "message": "计算中...",
        },
        target_done_step,
    ]

    if decision_only:
        steps.append(
            {
                "stage": "reconcile",
                "status": "done",
                "timestamp": now,
                "message": "仅决策模式，跳过执行",
            }
        )
    elif order_items:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "running",
                    "timestamp": now,
                    "message": "发送订单中...",
                },
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": now,
                    "items": order_items,
                },
                {
                    "stage": "reconcile",
                    "status": "running",
                    "timestamp": now,
                    "message": "核对执行结果...",
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": now,
                    "message": f"所有订单已确认，持仓已更新。模拟盈亏: {_format_pnl_label(daily_pnl)}",
                },
            ]
        )
    else:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": now,
                    "message": empty_messages.get("execute", "无可执行订单，已跳过模拟执行"),
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": now,
                    "message": empty_messages.get("reconcile", "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0"),
                },
            ]
        )

    return {
        "run_context_id": run_context_id,
        "started_at": now,
        "finished_at": now,
        "status": "completed",
        "steps": steps,
        "order_items": order_items,
    }


@router.post("/api/v1/dashboard/backtest")
def run_backtest(config: dict) -> dict:
    """快速回测：对 watchlist 股票运行日频确定性策略回测。"""
    watchlist = config.get("watchlist")
    if not watchlist:
        raise HTTPException(status_code=400, detail="watchlist is empty")
    start_str = config.get("start_date", "2025-01-01")
    end_str = config.get("end_date", "2025-03-31")
    capital_base = int(config.get("capital_base", 1_000_000))
    # 自动检测 market：从符号后缀推断，忽略前端可能不准确的 market 参数
    market = "us" if any(s.upper().endswith(".US") for s in watchlist) else config.get("market", "a")

    from src.backtest.engine import run_daily_backtest
    from src.backtest.metrics import calculate_metrics
    from src.indicators.technical_indicators import compute_features_from_bars
    from src.strategy.signal_engine import build_signal
    from src.strategy.strategy_config import StrategyConfig

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)

    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    # 提前 90 天取数据，确保有足够的历史窗口计算特征
    data_start = start_date - timedelta(days=120)

    # 根据市场类型选择数据源
    if market == "us":
        from src.us_stock.yahoo_provider import YahooProvider
        yahoo_provider = YahooProvider()
        use_yahoo = True
    else:
        provider = AkshareProvider()
        use_yahoo = False

    results = []
    for symbol in watchlist:
        try:
            if use_yahoo:
                # 美股：使用 YahooProvider 获取 K 线
                from datetime import timedelta as td
                period_days = (end_date - data_start).days
                if period_days <= 30:
                    period = "1mo"
                elif period_days <= 90:
                    period = "3mo"
                elif period_days <= 180:
                    period = "6mo"
                else:
                    period = "1y"
                klines = yahoo_provider.get_kline(symbol, interval="1d", range_str=period)
                if not klines:
                    continue
                # 转换为 backtest 格式
                bars = [
                    {
                        "date": k.timestamp.strftime("%Y-%m-%d") if hasattr(k.timestamp, "strftime") else str(k.timestamp)[:10],
                        "open": k.open,
                        "high": k.high,
                        "low": k.low,
                        "close": k.close,
                        "volume": k.volume,
                    }
                    for k in klines
                    if hasattr(k.timestamp, "strftime")
                ]
                # 过滤日期范围
                bars = [
                    b for b in bars
                    if data_start.strftime("%Y-%m-%d") <= b["date"] <= end_date.strftime("%Y-%m-%d")
                ]
            else:
                # A股：使用 AkshareProvider
                bars_df = provider.get_history(symbol, data_start, end_date)
                if bars_df.empty:
                    continue
                bars = bars_df.to_dict("records")

            if not bars:
                continue

            signals = []
            for i in range(60, len(bars)):
                window_bars = bars[max(0, i - 60):i + 1]
                features = compute_features_from_bars(window_bars)
                signal = build_signal(symbol, features, strategy_config)
                if signal["action"] != "HOLD":
                    signals.append({
                        "date": bars[i]["date"],
                        "action": signal["action"],
                        "target_position_ratio": settings.strategy_max_position_ratio if signal["action"] == "BUY" else 0.0,
                    })

            bt_result = run_daily_backtest(
                symbol=symbol,
                bars=bars,
                initial_cash=float(capital_base),
                signals=signals,
                lot_size=resolve_lot_size(
                    symbol=symbol,
                    lot_size_a=settings.strategy_lot_size_a,
                    lot_size_us=settings.strategy_lot_size_us,
                    market="US" if market == "us" else "CN_A",
                ),
                fee_bps=settings.strategy_fee_bps,
                slippage_bps=settings.strategy_slippage_bps,
            )
            metrics = calculate_metrics(bt_result["equity_curve"], bt_result["trades"])

            # 多因子分析：取最后一根 K 线的特征
            latest_features = compute_features_from_bars(bars)
            latest_signal = build_signal(symbol, latest_features, strategy_config)

            factor_details = {
                "features": latest_features,
                "technical_score": latest_signal["technical_score"],
                "action": latest_signal["action"],
                "weights": {
                    "momentum_20": 0.30,
                    "momentum_60": 0.25,
                    "ma20_gap": 0.20,
                    "ma60_gap": 0.15,
                    "volume_ratio_20": 0.10,
                    "volatility_20": -0.10,
                },
                "contributions": {
                    "momentum_20": round(0.30 * latest_features.get("momentum_20", 0), 6),
                    "momentum_60": round(0.25 * latest_features.get("momentum_60", 0), 6),
                    "ma20_gap": round(0.20 * latest_features.get("ma20_gap", 0), 6),
                    "ma60_gap": round(0.15 * latest_features.get("ma60_gap", 0), 6),
                    "volume_ratio_20": round(0.10 * latest_features.get("volume_ratio_20", 0), 6),
                    "volatility_20": round(-0.10 * latest_features.get("volatility_20", 0), 6),
                },
                "thresholds": {
                    "buy": strategy_config.buy_score_threshold,
                    "sell": strategy_config.sell_score_threshold,
                },
            }

            results.append({
                "symbol": symbol,
                "metrics": metrics,
                "trade_count": len(bt_result["trades"]),
                "final_nav": bt_result["final_nav"],
                "factor_analysis": factor_details,
            })
        except Exception as e:
            logger.warning(f"backtest({symbol}) failed: {e}")
            continue

    if not results:
        return {"status": "no_data", "results": [], "summary": {}}

    avg_return = sum(r["metrics"]["total_return"] for r in results) / len(results)
    worst_dd = min(r["metrics"]["max_drawdown"] for r in results)
    total_trades = sum(r["trade_count"] for r in results)

    return {
        "status": "ok",
        "start_date": start_str,
        "end_date": end_str,
        "results": results,
        "summary": {
            "total_return_avg": round(avg_return, 6),
            "max_drawdown_worst": round(worst_dd, 6),
            "total_trades": total_trades,
        },
    }


@router.post("/api/v1/dashboard/scan")
def scan_stock_pool(config: dict | None = None) -> dict:
    """全市场自动选股，扫描器预筛 + 历史K线确认。"""
    from datetime import datetime

    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    from src.strategy.stock_scanner import confirm_buy_candidates, scan_market
    from src.strategy.strategy_config import StrategyConfig

    cfg = config or {}
    top_n = int(cfg.get("top_n", 10))

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)
    provider = AkshareProvider()
    stock_list_df = provider.get_stock_list()
    stock_list = stock_list_df.to_dict("records")

    if not stock_list:
        return {"status": "no_catalog", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    # 第一轮：扫描器筛选（取 3x 候选给确认层）
    result = scan_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: _fetch_tencent_quotes_batch(syms),
        top_n=top_n * 3,
    )

    # 第二轮：用历史 K 线确认 BUY 候选
    def kline_fetcher(symbol, start, end):
        return provider.get_history(symbol, datetime.fromisoformat(start), datetime.fromisoformat(end))

    confirmed_buy = confirm_buy_candidates(
        result["buy"], kline_fetcher, strategy_config, top_n=top_n, as_of=datetime.now()
    )
    result["buy"] = confirmed_buy
    # HOLD/SELL 截断到 top_n（scan_market 取 3x 是给 BUY 确认用的）
    result["hold"] = result["hold"][:top_n]
    result["sell"] = result["sell"][:top_n]

    return {"status": "ok", **result}


@router.post("/api/v1/dashboard/scan-us")
def scan_us_stock_pool(config: dict | None = None) -> dict:
    """美股全市场自动选股，扫描器预筛 + 历史K线确认。"""
    from src.strategy.stock_scanner import confirm_us_buy_candidates, scan_us_market
    from src.us_stock.watchlist import WatchlistStore
    from src.us_stock.yahoo_provider import YahooProvider

    cfg = config or {}
    top_n = int(cfg.get("top_n", 10))

    # 获取美股watchlist
    import psycopg
    settings = Settings()
    database_url = settings.database_url
    if not database_url:
        return {"status": "no_database", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    from src.storage.connection_url import build_psycopg_dsn
    conn = psycopg.connect(build_psycopg_dsn(database_url), row_factory=psycopg.rows.dict_row)
    store = WatchlistStore(conn)
    stock_list_items, _ = store.list_items(page=1, page_size=1000)
    conn.close()

    if not stock_list_items:
        return {"status": "no_catalog", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    stock_list = [{"symbol": item.symbol, "name": item.name} for item in stock_list_items]

    # 初始化Yahoo数据源
    yahoo_provider = YahooProvider()

    # 第一轮：扫描器筛选（取 3x 候选给确认层）
    result = scan_us_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: yahoo_provider.get_quotes(syms),
        top_n=top_n * 3,
    )

    # 第二轮：用历史 K 线确认 BUY 候选
    def kline_fetcher(symbol, interval, range_str):
        return yahoo_provider.get_kline(symbol, interval, range_str)

    confirmed_buy = confirm_us_buy_candidates(
        result["buy"], kline_fetcher, top_n=top_n
    )
    result["buy"] = confirmed_buy
    # HOLD/SELL 截断到 top_n（scan_market 取 3x 是给 BUY 确认用的）
    result["hold"] = result["hold"][:top_n]
    result["sell"] = result["sell"][:top_n]

    return {"status": "ok", **result}


@router.get("/api/v1/dashboard/preferences")
def get_preferences(store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    """获取用户偏好设置（watchlist 等）。"""
    prefs = store.get_preference("dashboard") or {}
    if "theme_id" not in prefs:
        prefs["theme_id"] = "trading-terminal"
    return prefs


_THEME_IDS = {
    "trading-terminal", "mission-control", "neutral-modern", "hud-signal",
    "mono-grid", "openai-editorial", "nvidia-power", "coinbase-institutional",
}


@router.put("/api/v1/dashboard/preferences")
def save_preferences(config: dict, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    """保存用户偏好设置。"""
    allowed_keys = {"watchlist", "market", "capital_base", "max_position_ratio", "stop_loss_ratio",
                    "max_daily_loss_ratio", "execution_mode", "theme_id"}
    filtered = {k: v for k, v in config.items() if k in allowed_keys}
    if "theme_id" in filtered and filtered["theme_id"] not in _THEME_IDS:
        raise HTTPException(status_code=400, detail="invalid theme_id")
    # Merge with existing preferences
    existing = store.get_preference("dashboard") or {}
    merged = {**existing, **filtered}
    store.set_preference("dashboard", merged)
    return {"status": "ok"}



