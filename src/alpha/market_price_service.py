"""独立价格服务：最新价获取，供 portfolio_service 和 routes_alpha 共用。"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

_ALPHA_POSITION_PRICE_TTL_SECONDS = 300


def _is_us_symbol(symbol: str) -> bool:
    return symbol.upper().endswith(".US")


def _parse_to_utc(dt_str: str) -> datetime | None:
    """解析 ISO 时间字符串，统一转为 naive UTC datetime。"""
    try:
        parsed = datetime.fromisoformat(dt_str)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except (ValueError, TypeError):
        return None


class AlphaMarketPriceService:
    """最新价获取服务。美股走 quote，失败 fallback kline；A 股走 quote，失败 fallback history。"""

    def latest_close(self, symbol: str) -> float | None:
        """获取单个 symbol 的最新收盘价。失败返回 None。"""
        try:
            if _is_us_symbol(symbol):
                return self._us_latest_close(symbol)
            return self._a_latest_close(symbol)
        except Exception:
            logger.warning("latest_close(%s) failed", symbol, exc_info=True)
            return None

    def latest_closes(self, symbols: list[str]) -> dict[str, float]:
        """批量获取最新价。只返回成功获取的 symbol，失败的不包含在结果中。"""
        result: dict[str, float] = {}
        for symbol in symbols:
            price = self.latest_close(symbol)
            if price is not None and price > 0:
                result[symbol] = price
        return result

    @staticmethod
    def _us_latest_close(symbol: str) -> float | None:
        from src.us_stock.yahoo_provider import get_yahoo_provider

        provider = get_yahoo_provider()
        yahoo_symbol = symbol[:-3] if _is_us_symbol(symbol) else symbol
        # 优先 quote
        quote = provider.get_quote(yahoo_symbol)
        if quote and quote.price > 0:
            return float(quote.price)
        # fallback kline
        bars = provider.get_kline(yahoo_symbol, interval="1d", range_str="5d")
        if bars:
            return float(bars[-1].close)
        return None

    @staticmethod
    def _a_latest_close(symbol: str) -> float | None:
        from src.data.providers.akshare_provider import AkshareProvider

        provider = AkshareProvider()
        # 优先 quote
        try:
            snapshot = provider.get_realtime_quote(symbol)
            if snapshot and snapshot.close > 0:
                return float(snapshot.close)
        except Exception:
            logger.debug("a_latest_close quote failed for %s, falling back to history", symbol)
        # fallback history
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=10)
        bars = provider.get_history(symbol, start_date, end_date)
        if bars is not None and not getattr(bars, "empty", True):
            return float(bars.iloc[-1]["close"])
        return None


def find_stale_symbols(
    positions: list[dict],
    ttl_seconds: int = _ALPHA_POSITION_PRICE_TTL_SECONDS,
) -> list[str]:
    """找出需要刷新价格的 symbol 列表。"""
    now = datetime.utcnow()
    stale: list[str] = []
    for pos in positions:
        updated_at_str = pos.get("updated_at")
        mark_price = float(pos.get("mark_price", 0) or 0)
        if mark_price <= 0:
            stale.append(pos["symbol"])
            continue
        if not updated_at_str:
            stale.append(pos["symbol"])
            continue
        parsed = _parse_to_utc(updated_at_str)
        if parsed is None:
            stale.append(pos["symbol"])
            continue
        if (now - parsed).total_seconds() > ttl_seconds:
            stale.append(pos["symbol"])
    return stale


def is_stale(updated_at_str: str | None, ttl_seconds: int = _ALPHA_POSITION_PRICE_TTL_SECONDS) -> bool:
    """判断单个 position 是否价格过期。"""
    if not updated_at_str:
        return True
    parsed = _parse_to_utc(updated_at_str)
    if parsed is None:
        return True
    return (datetime.utcnow() - parsed).total_seconds() > ttl_seconds
