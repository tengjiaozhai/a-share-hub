import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.alpha.analysis_event_broadcaster import EventBroadcaster
from src.alpha.analysis_run_models import AnalysisRunCreateRequest
from src.alpha.analysis_run_service import (
    AlphaAnalysisConflictError,
    AlphaAnalysisNotFoundError,
    AlphaAnalysisRunService,
)
from src.alpha.analysis_run_store import AnalysisRunStore
from src.api.dependencies import (
    get_current_user,
    get_tenant_context,
    get_user_runtime_store,
)
from src.core.tenant import TenantContext
from src.storage.runtime_store import RuntimeStore

router = APIRouter(
    prefix="/api/v1/alpha",
    tags=["alpha"],
    dependencies=[Depends(get_current_user)],
)


_broadcaster: EventBroadcaster = EventBroadcaster()


def _normalize_holdings_entry(payload: dict) -> dict:
    from src.alpha.symbols import normalize_report_symbols

    symbol = normalize_report_symbols([payload.get("symbol")])
    buy_date = str(payload.get("buy_date") or "").strip()
    buy_price = float(payload.get("buy_price", 0.0) or 0.0)
    quantity = float(payload.get("quantity", 0.0) or 0.0)
    stop_loss_ratio = float(payload.get("stop_loss_ratio", -0.08) or -0.08)
    take_profit_ratio = float(payload.get("take_profit_ratio", 0.20) or 0.20)
    if not symbol or not buy_date or buy_price <= 0 or quantity <= 0:
        raise HTTPException(status_code=400, detail="invalid holdings entry")
    return {
        "symbol": symbol[0],
        "buy_date": buy_date,
        "buy_price": buy_price,
        "quantity": quantity,
        "stop_loss_ratio": stop_loss_ratio,
        "take_profit_ratio": take_profit_ratio,
    }


def _rebuild_holdings_portfolio(store: RuntimeStore) -> None:
    return None


def _build_run_store(store: RuntimeStore, user_id: str) -> AnalysisRunStore:
    return AnalysisRunStore(store.engine, TenantContext(user_id))


def _build_run_service(
    store: RuntimeStore, user_id: str, holdings_store: RuntimeStore
) -> AlphaAnalysisRunService:
    from src.agents.llm_client import LLMClient
    from src.alpha.analysis_agents import ResearchManager, Trader
    from src.alpha.analysis_snapshot import AnalysisSnapshotBuilder
    from src.core.config import Settings

    settings = Settings()
    llm = LLMClient(settings)

    def history_loader(symbol: str) -> list[dict]:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=120)
        try:
            if symbol.upper().endswith(".US"):
                from src.us_stock.yahoo_provider import YahooProvider

                klines = YahooProvider().get_kline(symbol[:-3], interval="1d", range_str="6mo")
                return [
                    {
                        "date": (
                            k.timestamp.strftime("%Y-%m-%d")
                            if hasattr(k.timestamp, "strftime")
                            else str(k.timestamp)[:10]
                        ),
                        "close": k.close,
                        "volume": k.volume,
                    }
                    for k in klines
                ]
            from src.data.providers.akshare_provider import AkshareProvider

            bars = AkshareProvider().get_history(symbol, start_date, end_date)
            if bars is None or getattr(bars, "empty", True):
                return []
            return bars.to_dict("records")
        except Exception:
            return []

    def fundamental_loader(symbol: str) -> dict:
        if symbol.upper().endswith(".US"):
            from src.us_stock.yahoo_provider import YahooProvider

            try:
                return YahooProvider().get_fundamental(symbol[:-3])
            except Exception:
                return {"status": "error"}
        return {"status": "ok"}

    snapshot_builder = AnalysisSnapshotBuilder(
        history_loader=history_loader,
        fundamental_loader=fundamental_loader,
    )
    return AlphaAnalysisRunService(
        store=_build_run_store(store, user_id),
        holdings_store=holdings_store,
        snapshot_builder=snapshot_builder,
        research_manager=ResearchManager(llm),
        trader=Trader(llm),
        broadcaster=_broadcaster,
        user_id=user_id,
        model_name=settings.llm_model,
        max_position_ratio=0.2,
    )


@router.post("/analysis-runs", status_code=202)
def start_analysis_run(
    payload: dict,
    background: BackgroundTasks,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    request = AnalysisRunCreateRequest(**payload)
    service = _build_run_service(store, tenant.user_id, store)
    try:
        response = service.start(request)
    except AlphaAnalysisConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "active_run_in_progress",
                "active_run_id": exc.active_run_id,
                "active_symbol": exc.active_symbol,
            },
        ) from exc
    except AlphaAnalysisNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if response["status"] == "accepted":
        background.add_task(_run_service_execute, service, response["run_id"])
    return response


async def _run_service_execute(service: AlphaAnalysisRunService, run_id: str) -> None:
    await service.execute(run_id)


@router.get("/analysis-runs")
def list_analysis_runs(
    market: str | None = None,
    status: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    run_store = _build_run_store(store, tenant.user_id)
    return run_store.list_runs(
        market=market,
        status_filter=status,
        limit=min(max(limit, 1), 100),
        cursor_run_id=cursor,
    )


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(
    run_id: str,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    run_store = _build_run_store(store, tenant.user_id)
    detail = run_store.get_run_detail(run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return detail


@router.get("/analysis-runs/{run_id}/events")
async def stream_analysis_run_events(
    run_id: str,
    request: Request,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
):
    run_store = _build_run_store(store, tenant.user_id)
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="analysis run not found")
    last_event_id_raw = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = int(last_event_id_raw)
    except ValueError:
        last_event_id = 0
    queue = _broadcaster.subscribe(run_id)
    return EventSourceResponse(
        _event_iter(run_id, queue, run_store, last_seq=last_event_id, symbol=run["symbol"])
    )


async def _event_iter(
    run_id: str,
    queue,
    run_store: AnalysisRunStore,
    last_seq: int,
    symbol: str,
) -> AsyncIterator[dict]:
    try:
        existing = run_store.list_events(run_id, after_seq=last_seq)
        for event in existing:
            payload = event.get("payload") or {}
            yield {
                "id": str(event["seq"]),
                "event": event["event_type"],
                "data": json.dumps(
                    {
                        "run_id": run_id,
                        "symbol": symbol,
                        "stage": event["stage"],
                        "status": event["status"],
                        "seq": event["seq"],
                        **payload,
                    },
                    ensure_ascii=False,
                ),
            }
            if event["stage"] in {"completed", "failed"}:
                return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                run = run_store.get_run(run_id)
                if run and run.get("status") in {"completed", "failed"}:
                    return
                continue
            yield {
                "id": str(event.get("seq", 0)),
                "event": event.get("stage", "stage"),
                "data": json.dumps(event, ensure_ascii=False),
            }
            if event.get("stage") in {"completed", "failed"}:
                return
    finally:
        _broadcaster.unsubscribe(run_id, queue)


@router.get("/holdings")
def list_holdings_entries(store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    return {"items": store.list_alpha_holdings_entries()}


@router.post("/holdings")
def create_holdings_entry(payload: dict, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    normalized = _normalize_holdings_entry(payload)
    entry_id = store.insert_alpha_holdings_entry(**normalized)
    _rebuild_holdings_portfolio(store)
    return next(item for item in store.list_alpha_holdings_entries() if item["entry_id"] == entry_id)


@router.put("/holdings/{entry_id}")
def update_holdings_entry(entry_id: str, payload: dict, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    normalized = _normalize_holdings_entry(payload)
    store.update_alpha_holdings_entry(entry_id=entry_id, **normalized)
    _rebuild_holdings_portfolio(store)
    for item in store.list_alpha_holdings_entries():
        if item["entry_id"] == entry_id:
            return item
    raise HTTPException(status_code=404, detail="holdings entry not found")


@router.delete("/holdings/{entry_id}")
def delete_holdings_entry(entry_id: str, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    store.delete_alpha_holdings_entry(entry_id)
    _rebuild_holdings_portfolio(store)
    return {"ok": True}


def _classify_market(symbol: str) -> str:
    return "us" if symbol.upper().endswith(".US") else "a"


@router.get("/holdings/summary")
def get_holdings_summary(store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    entries = store.list_alpha_holdings_entries()
    positions_by_symbol: dict[str, list[dict]] = {}
    for entry in entries:
        positions_by_symbol.setdefault(entry["symbol"], []).append(entry)

    aggregate: dict[str, dict] = {}

    for symbol, lots in positions_by_symbol.items():
        market = _classify_market(symbol)
        currency = "USD" if market == "us" else "CNY"
        total_cost = sum(float(lot["buy_price"]) * float(lot["quantity"]) for lot in lots)

        market_value = 0.0
        unrealized_pnl = 0.0

        bucket = aggregate.setdefault(
            market,
            {
                "market": market,
                "currency": currency,
                "holdings_count": 0,
                "lots_count": 0,
                "total_cost": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "_weighted_cost_sum": 0.0,
            },
        )
        bucket["holdings_count"] += 1
        bucket["lots_count"] += len(lots)
        bucket["total_cost"] += total_cost
        bucket["market_value"] += market_value
        bucket["unrealized_pnl"] += unrealized_pnl
        bucket["_weighted_cost_sum"] += total_cost

    summary: list[dict] = []
    for market_key in ("a", "us"):
        bucket = aggregate.get(market_key)
        if not bucket:
            summary.append(
                {
                    "market": market_key,
                    "currency": "USD" if market_key == "us" else "CNY",
                    "holdings_count": 0,
                    "lots_count": 0,
                    "total_cost": 0,
                    "market_value": 0,
                    "unrealized_pnl": 0,
                    "unrealized_pnl_ratio": 0,
                }
            )
            continue
        cost = bucket["_weighted_cost_sum"]
        ratio = bucket["unrealized_pnl"] / cost if cost > 0 else 0.0
        summary.append(
            {
                "market": bucket["market"],
                "currency": bucket["currency"],
                "holdings_count": bucket["holdings_count"],
                "lots_count": bucket["lots_count"],
                "total_cost": bucket["total_cost"],
                "market_value": bucket["market_value"],
                "unrealized_pnl": bucket["unrealized_pnl"],
                "unrealized_pnl_ratio": ratio,
            }
        )

    return {"summary": summary}
