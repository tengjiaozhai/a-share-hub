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


def _build_backtest_runner(engine, tenant: TenantContext, user_id: str):
    """构建回测运行器"""
    def runner(snapshot):
        from src.backtest.engine import run_daily_backtest
        from src.backtest.metrics import calculate_metrics
        from datetime import datetime, timedelta
        
        symbol = snapshot.symbol
        market = snapshot.market
        
        # 获取历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)  # 6个月回测
        
        if market == "us":
            from src.us_stock.yahoo_provider import get_yahoo_provider
            provider = get_yahoo_provider()
            # 去掉 .US 后缀，Yahoo Finance 不支持
            yahoo_symbol = symbol[:-3] if symbol.upper().endswith(".US") else symbol
            klines = provider.get_kline(yahoo_symbol, interval="1d", range_str="6mo")
            if not klines:
                return {"status": "error", "reason": "no historical data"}
            bars = [
                {
                    "date": k.timestamp.strftime("%Y-%m-%d"),
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
                for k in klines
            ]
            lot_size = 1
        else:
            from src.a_stock.akshare_provider import AkshareProvider
            provider = AkshareProvider()
            bars_df = provider.get_history(symbol, start_date, end_date)
            if bars_df.empty:
                return {"status": "error", "reason": "no historical data"}
            bars = bars_df.to_dict("records")
            lot_size = 100
        
        # 从 technical 指标生成交易信号
        signals = []
        technical = snapshot.technical or {}
        
        # 简单的信号生成逻辑：基于 RSI 和 MACD
        for i, bar in enumerate(bars):
            if i < 60:  # 需要足够的历史数据计算指标
                continue
            
            # 这里简化处理，实际应该计算技术指标
            # 暂时使用 HOLD 策略
            pass
        
        # 如果没有信号，使用买入持有策略
        if not signals and bars:
            signals = [{
                "date": bars[60]["date"],
                "action": "BUY",
                "target_position_ratio": 0.95,
            }]
        
        # 运行回测
        from src.core.config import Settings
        settings = Settings()
        bt_result = run_daily_backtest(
            symbol=symbol,
            bars=bars,
            initial_cash=1000000,  # 100万初始资金
            signals=signals,
            lot_size=lot_size,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
        )
        
        # 计算指标
        metrics = calculate_metrics(bt_result["equity_curve"], bt_result["trades"])
        
        return {
            "status": "completed",
            "symbol": symbol,
            "period": f"{bars[0]['date']} ~ {bars[-1]['date']}",
            "initial_cash": 1000000,
            "final_nav": bt_result["final_nav"],
            "total_return": metrics.get("total_return", 0),
            "annualized_return": metrics.get("annualized_return", 0),
            "max_drawdown": metrics.get("max_drawdown", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "win_rate": metrics.get("win_rate", 0),
            "trade_count": len(bt_result["trades"]),
            "trades": bt_result["trades"][:10],  # 只返回前10笔交易
        }
    
    return runner


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
    from src.alpha.market_price_service import AlphaMarketPriceService
    from src.alpha.portfolio_service import AlphaPortfolioService

    entries = store.list_alpha_holdings_entries()
    symbols = sorted({str(entry.get("symbol", "")).upper() for entry in entries if entry.get("symbol")})
    svc = AlphaMarketPriceService()
    price_map = svc.latest_closes(symbols)
    AlphaPortfolioService(store).rebuild_from_holdings_entries(price_map=price_map)


def _load_latest_close(symbol: str) -> float | None:
    """委托给 AlphaMarketPriceService，保留函数签名以兼容其他调用方。"""
    from src.alpha.market_price_service import AlphaMarketPriceService

    return AlphaMarketPriceService().latest_close(symbol)


def _build_run_store(store: RuntimeStore, user_id: str) -> AnalysisRunStore:
    return AnalysisRunStore(store.engine, TenantContext(user_id))


def _build_run_service(
    store: RuntimeStore, user_id: str, holdings_store: RuntimeStore, tenant: TenantContext
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
                from src.us_stock.yahoo_provider import get_yahoo_provider

                klines = get_yahoo_provider().get_kline(symbol[:-3], interval="1d", range_str="6mo")
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
            from src.us_stock.yahoo_provider import get_yahoo_provider

            try:
                fund = get_yahoo_provider().get_fundamental(symbol[:-3])
                return {
                    "status": "ok",
                    "pe_ratio": fund.pe_ratio,
                    "pb_ratio": fund.pb_ratio,
                    "eps": fund.eps,
                    "beta": fund.beta,
                    "market_cap": fund.market_cap,
                    "sector": fund.sector,
                    "industry": fund.industry,
                }
            except Exception:
                return {"status": "error"}
        return {"status": "ok"}

    def news_loader(symbol: str) -> dict:
        try:
            import akshare as ak
            raw = symbol[:-3] if symbol.upper().endswith(".US") else symbol
            df = ak.stock_news_em(symbol=raw)
            items = []
            for _, row in df.head(10).iterrows():
                items.append({
                    "title": str(row.get("新闻标题", "")),
                    "summary": str(row.get("新闻内容", ""))[:200],
                    "source": str(row.get("文章来源", "")),
                    "published_at": str(row.get("发布时间", "")),
                    "url": str(row.get("新闻链接", "")),
                })
            return {"status": "ok", "items": items}
        except Exception:
            return {"status": "error", "items": []}

    snapshot_builder = AnalysisSnapshotBuilder(
        history_loader=history_loader,
        fundamental_loader=fundamental_loader,
        news_loader=news_loader,
    )
    # 构建回测运行器
    backtest_runner = _build_backtest_runner(store.engine, tenant, user_id)
    
    return AlphaAnalysisRunService(
        store=_build_run_store(store, user_id),
        holdings_store=holdings_store,
        snapshot_builder=snapshot_builder,
        research_manager=ResearchManager(llm, model=settings.llm_model_research),
        trader=Trader(llm, model=settings.llm_model_trader),
        broadcaster=_broadcaster,
        backtest_runner=backtest_runner,
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
    service = _build_run_service(store, tenant.user_id, store, tenant)
    try:
        response = service.start(request)
    except AlphaAnalysisConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "active_run_in_progress",
                "active_run_id": exc.active_run_id,
                "active_symbol": exc.active_symbol,
            },
        ) from exc
    except AlphaAnalysisNotFoundError as exc:
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
                "event": event["stage"],
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
