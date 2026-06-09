import logging

from fastapi import APIRouter, HTTPException, Query

from src.us_stock.binance_asset import get_binance_us_assets
from src.us_stock.watchlist import WatchlistStore
from src.us_stock.yahoo_provider import YahooProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/us-stock", tags=["us-stock"])

_yahoo_provider: YahooProvider | None = None
_watchlist_store: WatchlistStore | None = None


def _get_yahoo_provider() -> YahooProvider:
    global _yahoo_provider
    if _yahoo_provider is None:
        _yahoo_provider = YahooProvider()
    return _yahoo_provider


def _get_watchlist_store() -> WatchlistStore:
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
        _watchlist_store = WatchlistStore(conn)
    return _watchlist_store


@router.get("/quotes")
def get_quotes() -> list[dict]:
    store = _get_watchlist_store()
    items = store.list_items()
    if not items:
        return []
    symbols = [item.symbol for item in items]
    provider = _get_yahoo_provider()
    quotes = provider.get_quotes(symbols)
    return [q.model_dump() for q in quotes]


@router.get("/quote/{symbol}")
def get_quote(symbol: str) -> dict:
    provider = _get_yahoo_provider()
    quote = provider.get_quote(symbol.upper())
    return quote.model_dump()


@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    interval: str = Query("1d"),
    range: str = Query("3mo"),  # noqa: A002 - matches Yahoo Finance API param name
) -> list[dict]:
    provider = _get_yahoo_provider()
    klines = provider.get_kline(symbol.upper(), interval=interval, range_str=range)
    return [k.model_dump() for k in klines]


@router.get("/fundamental/{symbol}")
def get_fundamental(symbol: str) -> dict:
    provider = _get_yahoo_provider()
    fund = provider.get_fundamental(symbol.upper())
    return fund.model_dump()


@router.get("/search")
def search(q: str = Query("", max_length=50)) -> list[dict]:
    if not q.strip():
        return []
    provider = _get_yahoo_provider()
    return provider.search(q)


@router.get("/watchlist")
def list_watchlist() -> list[dict]:
    store = _get_watchlist_store()
    items = store.list_items()
    return [item.model_dump() for item in items]


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


@router.get("/binance/assets")
def get_binance_assets() -> list[dict]:
    assets = get_binance_us_assets()
    return [a.model_dump() for a in assets]
