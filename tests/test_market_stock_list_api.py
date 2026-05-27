from fastapi.testclient import TestClient

from src.main import build_app


class FakeAkshareProvider:
    def __init__(self):
        pass

    def is_available(self):
        return True

    def get_stock_list(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
                {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
            ]
        )


def test_market_stocks_returns_filtered_records(monkeypatch):
    from src.api import routes_market

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: FakeAkshareProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/stocks", params={"query": "粮", "exchange": "SZ", "limit": 10})

    assert response.status_code == 200
    assert response.json() == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}
    ]
