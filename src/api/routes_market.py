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
