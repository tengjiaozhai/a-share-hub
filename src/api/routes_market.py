from fastapi import APIRouter, HTTPException, Query

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_provider import AkshareProvider

router = APIRouter(prefix="/api/v1/market")

_akshare_provider: AkshareProvider | None = None


def _get_akshare_provider() -> AkshareProvider:
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AkshareProvider()
    return _akshare_provider


@router.get("/stocks")
def list_market_stocks(
    query: str = Query("", max_length=50),
    exchange: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    frame = provider.get_stock_list()
    records = frame.copy()
    exchange_upper = exchange.strip().upper()
    if exchange_upper and exchange_upper != "ALL":
        records = records[records["exchange"] == exchange_upper]
    q = query.strip()
    if q:
        records = records[
            records["symbol"].str.contains(q, case=False, na=False)
            | records["code"].str.contains(q, case=False, na=False)
            | records["name"].str.contains(q, case=False, na=False)
        ]
    return records.head(limit).to_dict("records")


@router.get("/stocks/us")
def list_us_stocks(
    query: str = Query("", max_length=50),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    """获取美股知名股票列表，支持搜索过滤。"""
    try:
        import akshare as ak
        df = ak.stock_us_famous_spot_em()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取美股列表失败: {e}")

    # 标准化列名
    df = df.rename(columns={
        "名称": "name",
        "代码": "symbol",
        "最新价": "close",
        "涨跌额": "change",
        "涨跌幅": "change_pct",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "昨收价": "prev_close",
        "总市值": "market_cap",
        "市盈率": "pe_ratio",
    })

    # 搜索过滤
    q = query.strip()
    if q:
        df = df[
            df["symbol"].str.contains(q, case=False, na=False)
            | df["name"].str.contains(q, case=False, na=False)
        ]

    return df.head(limit).to_dict("records")


@router.get("/quote")
def get_market_quote(symbol: str = Query(..., min_length=3)) -> dict:
    normalized_symbol = symbol.strip().upper()
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    try:
        snapshot = provider.get_realtime_quote(normalized_symbol)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"quote symbol not found: {normalized_symbol}")
    except (AkshareUpstreamError, AkshareBreakerOpenError) as exc:
        raise HTTPException(status_code=503, detail=f"quote upstream unavailable: {exc}")
    return snapshot.model_dump()


@router.post("/bulk")
def get_bulk_quotes(symbols: list[str]) -> list[dict]:
    """批量获取行情，支持 200+ 只股票。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    if not symbols:
        return []
    df = _fetch_tencent_quotes_batch(symbols[:500])
    if df.empty:
        return []
    return df.to_dict("records")
