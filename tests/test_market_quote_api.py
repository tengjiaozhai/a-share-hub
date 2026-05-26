from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.data.providers.base import MarketSnapshot
from src.main import build_app


class FakeAkshareProvider:
    def __init__(self, *, available: bool, snapshot: MarketSnapshot | None):
        self._available = available
        self._snapshot = snapshot
        self.requested_symbol: str | None = None

    def is_available(self) -> bool:
        return self._available

    def get_realtime_quote(self, symbol: str) -> MarketSnapshot | None:
        self.requested_symbol = symbol
        return self._snapshot


def test_market_quote_returns_snapshot(monkeypatch):
    from src.api import routes_market

    provider = FakeAkshareProvider(
        available=True,
        snapshot=MarketSnapshot(
            symbol="600519.SH",
            timestamp=datetime.now(timezone.utc),
            open=1799.0,
            high=1810.0,
            low=1788.0,
            close=1805.5,
            volume=123456,
            amount=987654321.0,
            bid_price=1805.0,
            bid_volume=200,
            ask_price=1806.0,
            ask_volume=220,
        ),
    )
    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: provider)
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": " 600519.sh "})
    assert response.status_code == 200

    payload = response.json()
    assert provider.requested_symbol == "600519.SH"
    assert payload["symbol"] == "600519.SH"
    assert payload["close"] == 1805.5
    assert payload["open"] == 1799.0
    assert payload["volume"] == 123456
    assert "timestamp" in payload


def test_market_quote_returns_503_when_provider_unavailable(monkeypatch):
    from src.api import routes_market

    provider = FakeAkshareProvider(available=False, snapshot=None)
    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: provider)
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "600519.SH"})
    assert response.status_code == 503
    assert response.json()["detail"] == "akshare provider unavailable"


def test_market_quote_returns_404_when_symbol_missing(monkeypatch):
    from src.api import routes_market

    provider = FakeAkshareProvider(available=True, snapshot=None)
    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: provider)
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "600519.SH"})
    assert response.status_code == 404
    assert "quote not found" in response.json()["detail"]
