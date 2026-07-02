"""基金 API 路由"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_user, get_tenant_context
from src.core.tenant import TenantContext
from src.fund.catalog_service import FundCatalogService, FundNavUnavailableError, FundNotFoundError
from src.fund.watchlist import FundWatchlistStore
from src.storage.dependencies import get_runtime_engine

router = APIRouter(prefix="/api/v1/fund", dependencies=[Depends(get_current_user)])

_fund_catalog_service: FundCatalogService | None = None


def _get_fund_catalog_service() -> FundCatalogService:
    global _fund_catalog_service
    if _fund_catalog_service is None:
        _fund_catalog_service = FundCatalogService()
    return _fund_catalog_service


def _get_watchlist_store(tenant: TenantContext) -> FundWatchlistStore:
    engine = get_runtime_engine()
    return FundWatchlistStore(engine, tenant)


@router.get("/catalog")
def get_fund_catalog(
    query: str = Query("", description="搜索关键词（基金名称或代码）"),
    fund_type: str = Query("", description="基金类型筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页返回数量"),
) -> dict:
    """获取基金目录"""
    service = _get_fund_catalog_service()
    return service.search_funds(query=query, fund_type=fund_type, page=page, page_size=page_size)


@router.get("/catalog/{symbol}")
def get_fund_by_symbol(symbol: str) -> dict:
    """根据 symbol 获取基金信息"""
    service = _get_fund_catalog_service()
    fund = service.get_fund_by_symbol(symbol)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Fund {symbol} not found")
    return fund


@router.get("/watchlist")
def list_watchlist(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    store = _get_watchlist_store(tenant)
    items, total = store.list_items(page=page, page_size=page_size)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.post("/watchlist")
def add_to_watchlist(
    body: dict,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    symbol = body.get("symbol", "").strip().upper()
    name = body.get("name", "").strip()
    sort_order = int(body.get("sort_order", 0))
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol is required")

    if not name:
        fund = _get_fund_catalog_service().get_fund_by_symbol(symbol)
        name = str(fund.get("name") or symbol) if fund else symbol

    store = _get_watchlist_store(tenant)
    try:
        item = store.add(symbol, name, sort_order)
        return item.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(
    symbol: str,
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    normalized = symbol.upper()
    store = _get_watchlist_store(tenant)
    removed = store.remove(normalized)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Symbol {normalized} not found in watchlist")
    return {"removed": True, "symbol": normalized}


@router.get("/etf/spot")
def get_etf_spot(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页返回数量"),
    query: str = Query("", description="搜索关键词（基金代码或名称）"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> dict:
    """获取 ETF 实时行情（带缓存）"""
    service = _get_fund_catalog_service()
    return service.get_etf_spot(page=page, page_size=page_size, query=query, force_refresh=force_refresh)


@router.get("/nav/{symbol}")
def get_fund_nav(
    symbol: str,
    start_date: str = Query("", description="开始日期 (YYYYMMDD)"),
    end_date: str = Query("", description="结束日期 (YYYYMMDD)"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> list[dict]:
    """获取基金历史净值（带缓存）"""
    service = _get_fund_catalog_service()
    try:
        return service.get_fund_nav(
            symbol=symbol, start_date=start_date, end_date=end_date,
            force_refresh=force_refresh
        )
    except FundNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FundNavUnavailableError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "symbol": exc.symbol,
                "reason": exc.reason,
            },
        ) from exc


@router.get("/etf/history/{symbol}")
def get_etf_history(
    symbol: str,
    period: str = Query("daily", description="周期 (daily/weekly/monthly)"),
    start_date: str = Query("", description="开始日期 (YYYYMMDD)"),
    end_date: str = Query("", description="结束日期 (YYYYMMDD)"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> list[dict]:
    """获取 ETF 历史行情（带缓存）"""
    service = _get_fund_catalog_service()
    return service.get_etf_history(
        symbol=symbol, period=period,
        start_date=start_date, end_date=end_date,
        force_refresh=force_refresh
    )


@router.get("/cache/stats")
def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    service = _get_fund_catalog_service()
    return service.get_cache_stats()


@router.post("/cache/clear")
def clear_cache(
    cache_type: str = Query("all", description="缓存类型 (etf_spot/fund_nav/etf_history/catalog/all)"),
) -> dict:
    """清除缓存"""
    service = _get_fund_catalog_service()
    service.clear_cache(cache_type=cache_type)
    return {"message": f"Cache '{cache_type}' cleared successfully"}


@router.get("/analysis/performance/{symbol}")
def get_fund_performance(
    symbol: str,
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> dict:
    """获取基金业绩分析"""
    from src.fund.analysis_service import FundAnalysisService
    service = FundAnalysisService()
    return service.get_fund_performance(symbol=symbol, force_refresh=force_refresh)


@router.post("/analysis/compare")
def compare_funds(
    symbols: list[str],
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> dict:
    """对比多个基金"""
    from src.fund.analysis_service import FundAnalysisService
    service = FundAnalysisService()
    return service.compare_funds(symbols=symbols, force_refresh=force_refresh)


@router.get("/analysis/screen")
def screen_funds(
    fund_type: str = Query("", description="基金类型"),
    min_return_1y: float = Query(None, description="最低1年收益率"),
    max_drawdown: float = Query(None, description="最大回撤限制"),
    min_sharpe: float = Query(None, description="最低夏普比率"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> list[dict]:
    """筛选基金"""
    from src.fund.analysis_service import FundAnalysisService
    service = FundAnalysisService()
    return service.screen_funds(
        fund_type=fund_type,
        min_return_1y=min_return_1y,
        max_drawdown=max_drawdown,
        min_sharpe=min_sharpe,
        limit=limit,
        force_refresh=force_refresh,
    )


@router.get("/analysis/rating/{symbol}")
def get_fund_rating(symbol: str) -> dict:
    """获取基金评级"""
    from src.fund.analysis_service import FundAnalysisService
    service = FundAnalysisService()
    return service.get_fund_rating(symbol=symbol)
