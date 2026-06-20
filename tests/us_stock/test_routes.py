from unittest.mock import MagicMock, patch

from src.main import build_app


def test_get_watchlist(authenticated_client, monkeypatch):
    with patch("src.us_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = ([], 0)
        mock_store.return_value = mock_instance
        resp = authenticated_client.get("/api/v1/us-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
    assert resp.json()["items"] == []


def test_search_empty_query(authenticated_client):
    resp = authenticated_client.get("/api/v1/us-stock/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_quote_not_found(authenticated_client):
    with patch("src.us_stock.routes._get_yahoo_provider") as mock_prov:
        mock_instance = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = 0.0
        mock_quote.symbol = "INVALID"
        mock_quote.name = "INVALID"
        mock_quote.model_dump.return_value = {"symbol": "INVALID", "name": "INVALID", "price": 0.0}
        mock_instance.get_quote.return_value = mock_quote
        mock_prov.return_value = mock_instance
        resp = authenticated_client.get("/api/v1/us-stock/quote/INVALID")
    assert resp.status_code == 200
    data = resp.json()
    assert data["price"] == 0.0
