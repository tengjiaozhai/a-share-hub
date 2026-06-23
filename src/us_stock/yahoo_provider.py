import logging
import time
from datetime import datetime

import yfinance as yf

from src.us_stock.cache import TTLMemoryCache
from src.us_stock.models import USFundamental, USKline, USQuote

logger = logging.getLogger(__name__)

_VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}
_VALID_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}


class YahooProvider:
    """yfinance 封装，带内存缓存。"""

    def __init__(
        self,
        cache_ttl_quote: int = 120,
        cache_ttl_kline: int = 600,
        cache_ttl_fundamental: int = 3600,
        batch_size: int = 50,
        batch_delay: float = 0.5,
    ):
        self._quote_cache = TTLMemoryCache(ttl_seconds=cache_ttl_quote)
        self._kline_cache = TTLMemoryCache(ttl_seconds=cache_ttl_kline)
        self._fundamental_cache = TTLMemoryCache(ttl_seconds=cache_ttl_fundamental)
        self._search_cache = TTLMemoryCache(ttl_seconds=600)
        self._batch_size = batch_size
        self._batch_delay = batch_delay

    def get_quote(self, symbol: str) -> USQuote:
        cached = self._quote_cache.get(f"quote:{symbol}")
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as e:
            logger.warning(f"yfinance get_quote({symbol}) failed: {e}")
            return USQuote(symbol=symbol, name=symbol)

        if not info or not info.get("regularMarketPrice"):
            return USQuote(symbol=symbol, name=symbol)

        market_state = info.get("marketState", "")
        quote = USQuote(
            symbol=symbol,
            name=info.get("shortName", symbol),
            price=float(info.get("regularMarketPrice", 0)),
            change=float(info.get("regularMarketChange", 0)),
            change_pct=float(info.get("regularMarketChangePercent", 0)),
            open=float(info.get("regularMarketOpen", 0)),
            high=float(info.get("regularMarketDayHigh", 0)),
            low=float(info.get("regularMarketDayLow", 0)),
            volume=int(info.get("regularMarketVolume", 0)),
            market_cap=int(info.get("marketCap", 0)),
            prev_close=float(info.get("regularMarketPreviousClose", 0)),
            market_open=market_state in {"REGULAR", "PRE", "POST"},
            stale=False,
            updated_at=datetime.now(),
        )
        self._quote_cache.set(f"quote:{symbol}", quote)
        return quote

    def get_quotes(self, symbols: list[str]) -> list[USQuote]:
        results: list[USQuote] = []
        uncached: list[str] = []

        for sym in symbols:
            cached = self._quote_cache.get(f"quote:{sym}")
            if cached is not None:
                results.append(cached)
            else:
                uncached.append(sym)

        if not uncached:
            return results

        # 批量获取价格和成交量
        try:
            df = yf.download(uncached, period="1d", group_by="ticker", progress=False, threads=True)
        except Exception as e:
            logger.warning(f"yf.download batch failed: {e}, falling back to per-symbol")
            df = None

        if df is not None and not df.empty:
            for sym in uncached:
                try:
                    if len(uncached) == 1:
                        row = df.iloc[-1] if not df.empty else None
                    else:
                        sym_df = df[sym] if sym in df.columns.get_level_values(0) else None
                        row = sym_df.iloc[-1] if sym_df is not None and not sym_df.empty else None

                    if row is not None:
                        close = float(row.get("Close", 0))
                        open_p = float(row.get("Open", 0))
                        high = float(row.get("High", 0))
                        low = float(row.get("Low", 0))
                        volume = int(row.get("Volume", 0))
                        change = close - open_p if open_p else 0
                        change_pct = (change / open_p * 100) if open_p else 0

                        quote = USQuote(
                            symbol=sym,
                            name=sym,
                            price=round(close, 2),
                            change=round(change, 2),
                            change_pct=round(change_pct, 2),
                            open=round(open_p, 2),
                            high=round(high, 2),
                            low=round(low, 2),
                            volume=volume,
                            market_cap=0,  # 批量获取时无法获取market_cap
                            prev_close=0,
                            market_open=True,
                            stale=False,
                            updated_at=datetime.now(),
                        )
                        self._quote_cache.set(f"quote:{sym}", quote)
                        results.append(quote)
                    else:
                        results.append(USQuote(symbol=sym, name=sym))
                except Exception as e:
                    logger.warning(f"get_quotes({sym}) parse failed: {e}")
                    results.append(USQuote(symbol=sym, name=sym))
        else:
            # fallback: 逐个获取
            for sym in uncached:
                try:
                    quote = self.get_quote(sym)
                    results.append(quote)
                except Exception as e:
                    logger.warning(f"get_quotes({sym}) failed: {e}")
                    results.append(USQuote(symbol=sym, name=sym))

        return results

    def get_kline(self, symbol: str, interval: str = "1d", range_str: str = "3mo") -> list[USKline]:
        if interval not in _VALID_INTERVALS:
            interval = "1d"
        if range_str not in _VALID_RANGES:
            range_str = "3mo"

        cache_key = f"kline:{symbol}:{interval}:{range_str}"
        cached = self._kline_cache.get(cache_key)
        if cached is not None:
            logger.info(f"yfinance get_kline({symbol}) cache hit")
            return cached

        # 增强重试逻辑：最多重试5次，指数退避
        df = None
        max_retries = 5
        for attempt in range(max_retries):
            try:
                logger.info(f"yfinance get_kline({symbol}) attempt {attempt + 1}/{max_retries}")
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=range_str, interval=interval)
                if not df.empty:
                    logger.info(f"yfinance get_kline({symbol}) success: {len(df)} records")
                    break
                else:
                    logger.warning(f"yfinance get_kline({symbol}) returned empty data")
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"yfinance get_kline({symbol}) attempt {attempt + 1} failed: {error_msg}")
                if attempt < max_retries - 1:
                    # 指数退避：2s, 4s, 8s, 16s
                    wait_time = (2 ** (attempt + 1))
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"yfinance get_kline({symbol}) all {max_retries} attempts failed")
                    return []

        if df is None or df.empty:
            logger.error(f"yfinance get_kline({symbol}) final result is empty")
            return []

        klines = []
        for ts, row in df.iterrows():
            klines.append(USKline(
                symbol=symbol,
                interval=interval,
                open=float(row.get("Open", 0)),
                high=float(row.get("High", 0)),
                low=float(row.get("Low", 0)),
                close=float(row.get("Close", 0)),
                volume=int(row.get("Volume", 0)),
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(),
            ))

        self._kline_cache.set(cache_key, klines)
        return klines

    def get_fundamental(self, symbol: str) -> USFundamental:
        cached = self._fundamental_cache.get(f"fund:{symbol}")
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as e:
            logger.warning(f"yfinance get_fundamental({symbol}) failed: {e}")
            return USFundamental(symbol=symbol)

        if not info:
            return USFundamental(symbol=symbol)

        fundamental = USFundamental(
            symbol=symbol,
            name=info.get("shortName", ""),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            market_cap=int(info.get("marketCap", 0)),
            pe_ratio=float(info.get("trailingPE", 0) or 0),
            pb_ratio=float(info.get("priceToBook", 0) or 0),
            dividend_yield=float(info.get("dividendYield", 0) or 0),
            eps=float(info.get("trailingEps", 0) or 0),
            beta=float(info.get("beta", 0) or 0),
            fifty_two_week_high=float(info.get("fiftyTwoWeekHigh", 0) or 0),
            fifty_two_week_low=float(info.get("fiftyTwoWeekLow", 0) or 0),
        )
        self._fundamental_cache.set(f"fund:{symbol}", fundamental)
        return fundamental

    def search(self, query: str) -> list[dict]:
        if not query or len(query.strip()) < 1:
            return []

        cache_key = f"search:{query.lower().strip()}"
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            srch = yf.Search(query)
            quotes = srch.quotes or []
        except Exception as e:
            logger.warning(f"yfinance search({query}) failed: {e}")
            return []

        results = []
        for q in quotes[:20]:
            results.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            })

        self._search_cache.set(cache_key, results)
        return results

    def is_market_open(self) -> bool:
        now = datetime.utcnow()
        weekday = now.weekday()
        if weekday >= 5:
            return False
        hour = now.hour
        return 13 <= hour < 20


# 模块级单例，避免重复创建实例导致缓存失效和 Yahoo API 限流
_shared_provider: "YahooProvider | None" = None


def get_yahoo_provider() -> YahooProvider:
    """获取共享的 YahooProvider 单例实例。"""
    global _shared_provider
    if _shared_provider is None:
        _shared_provider = YahooProvider()
    return _shared_provider
