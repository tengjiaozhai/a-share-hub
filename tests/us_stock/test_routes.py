from unittest.mock import MagicMock, patch

from src.us_stock import routes


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


def test_get_quotes_reuse_polling_cache(authenticated_client):
    routes._quotes_cache.clear()
    item = MagicMock()
    item.symbol = "AAPL"
    quote = MagicMock()
    quote.model_dump.return_value = {"symbol": "AAPL", "price": 100.0}

    with patch("src.us_stock.routes._get_watchlist_store") as mock_store:
        mock_store.return_value.list_items.return_value = ([item], 1)
        with patch("src.us_stock.routes._get_yahoo_provider") as mock_provider:
            mock_provider.return_value.get_quotes.return_value = [quote]
            first = authenticated_client.get("/api/v1/us-stock/quotes")
            second = authenticated_client.get("/api/v1/us-stock/quotes")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert mock_provider.return_value.get_quotes.call_count == 1
