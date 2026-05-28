from fastapi.testclient import TestClient
from src.main import build_app


def test_backtest_endpoint_returns_metrics(monkeypatch):
    import pandas as pd
    from src.api import routes_dashboard

    mock_bars = [
        {"date": "2025-01-02", "open": 100.0, "close": 102.0, "high": 103.0, "low": 99.0, "volume": 1000},
        {"date": "2025-01-03", "open": 102.0, "close": 104.0, "high": 105.0, "low": 101.0, "volume": 1200},
    ]

    def mock_get_history(self, symbol, start_date, end_date, freq="daily"):
        return pd.DataFrame(mock_bars)

    from src.data.providers.akshare_provider import AkshareProvider
    monkeypatch.setattr(AkshareProvider, "get_history", mock_get_history)

    client = TestClient(build_app())
    response = client.post("/api/v1/dashboard/backtest", json={
        "watchlist": ["600519.SH"],
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "capital_base": 1000000,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["results"]) == 1
    assert "metrics" in data["results"][0]
    assert "total_return" in data["results"][0]["metrics"]


def test_backtest_endpoint_returns_400_for_empty_watchlist():
    client = TestClient(build_app())
    response = client.post("/api/v1/dashboard/backtest", json={
        "watchlist": [],
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "capital_base": 1000000,
    })
    assert response.status_code == 400
