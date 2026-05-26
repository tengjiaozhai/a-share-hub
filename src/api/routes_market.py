from fastapi import APIRouter, HTTPException, Query

from src.data.providers.akshare_provider import AkshareProvider

router = APIRouter(prefix="/api/v1/market")

_akshare_provider: AkshareProvider | None = None


def _get_akshare_provider() -> AkshareProvider:
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AkshareProvider()
    return _akshare_provider


@router.get("/quote")
def get_market_quote(symbol: str = Query(..., min_length=3)) -> dict:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")

    snapshot = provider.get_realtime_quote(normalized_symbol)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"quote not found: {normalized_symbol}")

    return snapshot.model_dump()
