from unittest.mock import MagicMock, patch

from src.us_stock.yahoo_provider import YahooProvider


def test_get_quote_returns_us_quote():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 195.2,
        "regularMarketChange": 2.5,
        "regularMarketChangePercent": 1.3,
        "regularMarketOpen": 193.0,
        "regularMarketDayHigh": 196.0,
        "regularMarketDayLow": 192.5,
        "regularMarketVolume": 52000000,
        "marketCap": 3000000000000,
        "regularMarketPreviousClose": 192.7,
        "marketState": "REGULAR",
    }
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        quote = provider.get_quote("AAPL")
    assert quote.symbol == "AAPL"
    assert quote.name == "Apple Inc."
    assert quote.price == 195.2
    assert quote.market_open is True


def test_get_quote_symbol_not_found():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        quote = provider.get_quote("INVALID123")
    assert quote.price == 0.0


def test_get_quote_uses_cache():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Test",
        "regularMarketPrice": 100.0,
        "marketState": "REGULAR",
    }
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker) as mock_ticker_cls:
        q1 = provider.get_quote("TEST")
        q2 = provider.get_quote("TEST")
    assert q1.price == 100.0
    assert q2.price == 100.0
    assert mock_ticker_cls.call_count == 1  # 第二次走缓存，不再创建 Ticker


def test_search_returns_results():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_search = MagicMock()
    mock_search.quotes = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NASDAQ", "quoteType": "EQUITY"},
    ]
    with patch("src.us_stock.yahoo_provider.yf.Search", return_value=mock_search):
        results = provider.search("Apple")
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"


def test_get_kline_returns_list():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    import pandas as pd
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame({
        "Open": [190.0, 191.0],
        "High": [192.0, 193.0],
        "Low": [189.0, 190.0],
        "Close": [191.5, 192.5],
        "Volume": [50000000, 51000000],
    }, index=pd.to_datetime(["2026-01-01", "2026-01-02"]))
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        klines = provider.get_kline("AAPL", interval="1d", range_str="5d")
    assert len(klines) == 2
    assert klines[0].symbol == "AAPL"
    assert klines[0].close == 191.5
