import logging

from fastapi import APIRouter, HTTPException, Query

from src.a_stock.watchlist import AShareWatchlistStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/a-stock", tags=["a-stock"])

_watchlist_store: AShareWatchlistStore | None = None


def _get_watchlist_store() -> AShareWatchlistStore:
    global _watchlist_store
    if _watchlist_store is None:
        import psycopg

        from src.core.config import Settings
        from src.storage.connection_url import build_psycopg_dsn
        settings = Settings()
        database_url = settings.database_url
        if not database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        conn = psycopg.connect(build_psycopg_dsn(database_url), row_factory=psycopg.rows.dict_row)
        _watchlist_store = AShareWatchlistStore(conn)
    return _watchlist_store


@router.get("/watchlist")
def list_watchlist(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
) -> dict:
    store = _get_watchlist_store()
    items, total = store.list_items(page=page, page_size=page_size)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.post("/watchlist")
def add_to_watchlist(body: dict) -> dict:
    symbol = body.get("symbol", "").strip().upper()
    name = body.get("name", "").strip()
    sort_order = int(body.get("sort_order", 0))
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol is required")
    store = _get_watchlist_store()
    try:
        item = store.add(symbol, name or symbol, sort_order)
        return item.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str) -> dict:
    store = _get_watchlist_store()
    removed = store.remove(symbol.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in watchlist")
    return {"removed": True, "symbol": symbol.upper()}


@router.post("/quotes")
def get_quotes(symbols: list[str]) -> list[dict]:
    """批量获取 A 股行情。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    if not symbols:
        return []
    df = _fetch_tencent_quotes_batch(symbols[:500])
    if df.empty:
        return []
    return df.to_dict("records")


@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    period: str = Query("daily"),
    count: int = Query(60, ge=1, le=500),
) -> list[dict]:
    """获取 A 股 K 线数据。"""
    from datetime import datetime, timedelta

    from src.data.providers.akshare_provider import AkshareProvider

    normalized = symbol.strip().upper()
    provider = AkshareProvider()

    end_date = datetime.now()
    if period == "daily":
        start_date = end_date - timedelta(days=count * 2)
    elif period == "weekly":
        start_date = end_date - timedelta(days=count * 10)
    else:
        start_date = end_date - timedelta(days=count * 30)

    try:
        df = provider.get_history(normalized, start_date, end_date, freq=period)
    except Exception as e:
        logger.warning(f"get_kline({normalized}) failed: {e}")
        raise HTTPException(status_code=503, detail=f"K line data unavailable: {e}") from e

    if df.empty:
        return []

    records = df.tail(count).to_dict("records")
    return [
        {
            "date": str(r.get("date", "")),
            "open": float(r.get("open", 0)),
            "high": float(r.get("high", 0)),
            "low": float(r.get("low", 0)),
            "close": float(r.get("close", 0)),
            "volume": int(r.get("volume", 0)),
        }
        for r in records
    ]


@router.get("/fundamental/{symbol}")
def get_fundamental(symbol: str) -> dict:
    """获取 A 股基本面数据。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch

    normalized = symbol.strip().upper()
    df = _fetch_tencent_quotes_batch([normalized])

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    row = df.iloc[0]
    return {
        "symbol": normalized,
        "name": str(row.get("name", "")),
        "pe_ratio": float(row.get("pe_ratio", 0) or 0),
        "turnover": float(row.get("turnover", 0) or 0),
        "amplitude": float(row.get("amplitude", 0) or 0),
        "volume_ratio": float(row.get("volume_ratio", 0) or 0),
        "market_cap": 0.0,
        "high_52w": 0.0,
        "low_52w": 0.0,
    }
