from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.main import build_app


client = TestClient(build_app())


def test_get_watchlist():
    with patch("src.us_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = []
        mock_store.return_value = mock_instance
        resp = client.get("/api/v1/us-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_search_empty_query():
    resp = client.get("/api/v1/us-stock/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_quote_not_found():
    with patch("src.us_stock.routes._get_yahoo_provider") as mock_prov:
        mock_instance = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = 0.0
        mock_quote.symbol = "INVALID"
        mock_quote.name = "INVALID"
        mock_quote.model_dump.return_value = {"symbol": "INVALID", "name": "INVALID", "price": 0.0}
        mock_instance.get_quote.return_value = mock_quote
        mock_prov.return_value = mock_instance
        resp = client.get("/api/v1/us-stock/quote/INVALID")
    assert resp.status_code == 200
    data = resp.json()
    assert data["price"] == 0.0
