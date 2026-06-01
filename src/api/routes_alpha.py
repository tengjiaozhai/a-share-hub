from fastapi import APIRouter

from src.alpha.binance_public_client import BinanceAlphaPublicClient
from src.alpha.service import AlphaMarketService

router = APIRouter(prefix="/api/v1/alpha", tags=["alpha"])
_service: AlphaMarketService | None = None


def _get_alpha_market_service() -> AlphaMarketService:
    global _service
    if _service is None:
        import httpx

        client = httpx.AsyncClient(base_url="https://www.binance.com")
        _service = AlphaMarketService(BinanceAlphaPublicClient(client))
    return _service


@router.get("/assets")
async def list_alpha_assets() -> dict:
    snapshots = await _get_alpha_market_service().list_asset_snapshots()
    return {
        "items": [
            {
                "symbol": item.symbol,
                "underlying_symbol": item.underlying_symbol,
                "project_id": item.project_id,
                "market_status": item.market_status,
                "asset_status": item.asset_status,
                "shares_multiplier": item.shares_multiplier,
                "min_qty": item.min_qty,
                "max_qty": item.max_qty,
            }
            for item in snapshots
        ]
    }
