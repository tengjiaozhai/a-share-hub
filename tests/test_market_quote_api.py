from fastapi.testclient import TestClient

from src.main import build_app


def test_market_quote_returns_404_for_unknown_symbol(monkeypatch):
    from src.api import routes_market

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise KeyError(symbol)

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "999999.SH"})

    assert response.status_code == 404
    assert response.json()["detail"] == "quote symbol not found: 999999.SH"


def test_market_quote_returns_503_for_upstream_failure(monkeypatch):
    from src.api import routes_market
    from src.data.providers.akshare_errors import AkshareUpstreamError

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise AkshareUpstreamError("upstream reset")

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "000858.SZ"})

    assert response.status_code == 503
    assert response.json()["detail"] == "quote upstream unavailable: upstream reset"


def test_market_quote_returns_503_when_breaker_is_open(monkeypatch):
    from src.api import routes_market
    from src.data.providers.akshare_errors import AkshareBreakerOpenError

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise AkshareBreakerOpenError("akshare spot snapshot breaker is open")

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "000858.SZ"})

    assert response.status_code == 503
    assert response.json()["detail"] == "quote upstream unavailable: akshare spot snapshot breaker is open"


def test_provider_raises_key_error_only_for_missing_symbol(monkeypatch):
    import pandas as pd
    import pytest
    from src.data.providers.akshare_catalog import StockCatalogCache
    from src.data.providers.akshare_provider import AkshareProvider
    from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache

    catalog = StockCatalogCache(ttl_seconds=300)
    snapshot_cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=3, open_seconds=30)
    provider = AkshareProvider(catalog=catalog, snapshot_cache=snapshot_cache)

    monkeypatch.setattr(
        provider,
        "get_stock_list",
        lambda: pd.DataFrame([{"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}]),
    )

    with pytest.raises(KeyError):
        provider.get_realtime_quote("999999.SH")
