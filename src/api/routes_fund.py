"""基金 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.dependencies import get_current_user
from src.fund.catalog_service import FundCatalogService

router = APIRouter(prefix="/api/v1/fund", dependencies=[Depends(get_current_user)])

_fund_catalog_service: FundCatalogService | None = None


def _get_fund_catalog_service() -> FundCatalogService:
    global _fund_catalog_service
    if _fund_catalog_service is None:
        _fund_catalog_service = FundCatalogService()
    return _fund_catalog_service


@router.get("/catalog")
def get_fund_catalog(
    query: str = Query("", description="搜索关键词（基金名称或代码）"),
    fund_type: str = Query("", description="基金类型筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
) -> list[dict]:
    """获取基金目录"""
    service = _get_fund_catalog_service()
    return service.search_funds(query=query, fund_type=fund_type, limit=limit)


@router.get("/catalog/{symbol}")
def get_fund_by_symbol(symbol: str) -> dict:
    """根据 symbol 获取基金信息"""
    service = _get_fund_catalog_service()
    fund = service.get_fund_by_symbol(symbol)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Fund {symbol} not found")
    return fund


@router.get("/etf/spot")
def get_etf_spot(
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> list[dict]:
    """获取 ETF 实时行情（带缓存）"""
    service = _get_fund_catalog_service()
    return service.get_etf_spot(limit=limit, force_refresh=force_refresh)


@router.get("/nav/{symbol}")
def get_fund_nav(
    symbol: str,
    start_date: str = Query("", description="开始日期 (YYYYMMDD)"),
    end_date: str = Query("", description="结束日期 (YYYYMMDD)"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
) -> list[dict]:
    """获取基金历史净值（带缓存）"""
    service = _get_fund_catalog_service()
    return service.get_fund_nav(
        symbol=symbol, start_date=start_date, end_date=end_date,
        force_refresh=force_refresh
    )


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
