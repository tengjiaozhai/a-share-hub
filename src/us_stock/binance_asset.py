import logging
import os

from src.crypto.data.binance_provider import BinanceProvider
from src.us_stock.cache import TTLMemoryCache
from src.us_stock.models import USBinanceAsset

logger = logging.getLogger(__name__)

_cache = TTLMemoryCache(ttl_seconds=30)


def get_binance_us_assets() -> list[USBinanceAsset]:
    """查询币安账户中的美股资产。"""
    cached = _cache.get("binance_assets")
    if cached is not None:
        return cached

    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        return []

    try:
        provider = BinanceProvider(api_key=api_key, api_secret=api_secret, testnet=False)
        import asyncio
        account = asyncio.run(provider._request("GET", "/api/v3/account", signed=True))
    except Exception as e:
        logger.warning(f"Binance account query failed: {e}")
        return []

    balances = account.get("balances", [])
    assets = []
    for b in balances:
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        total = free + locked
        if total <= 0:
            continue
        asset = b.get("asset", "")
        if len(asset) <= 5 and asset.isalpha():
            assets.append(USBinanceAsset(
                symbol=asset,
                free=free,
                locked=locked,
                total=total,
                usdt_value=0.0,
            ))

    _cache.set("binance_assets", assets)
    return assets
