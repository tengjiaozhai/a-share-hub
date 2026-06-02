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
        cache_ttl_quote: int = 60,
        cache_ttl_kline: int = 300,
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

        for i in range(0, len(uncached), self._batch_size):
            batch = uncached[i : i + self._batch_size]
            for sym in batch:
                try:
                    quote = self.get_quote(sym)
                    results.append(quote)
                except Exception as e:
                    logger.warning(f"get_quotes({sym}) failed: {e}")
                    results.append(USQuote(symbol=sym, name=sym))
            if i + self._batch_size < len(uncached):
                time.sleep(self._batch_delay)

        return results

    def get_kline(self, symbol: str, interval: str = "1d", range_str: str = "3mo") -> list[USKline]:
        if interval not in _VALID_INTERVALS:
            interval = "1d"
        if range_str not in _VALID_RANGES:
            range_str = "3mo"

        cache_key = f"kline:{symbol}:{interval}:{range_str}"
        cached = self._kline_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=range_str, interval=interval)
        except Exception as e:
            logger.warning(f"yfinance get_kline({symbol}) failed: {e}")
            return []

        if df.empty:
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
