from unittest.mock import MagicMock, patch

import pandas as pd

from src.a_stock import routes


def test_get_watchlist(authenticated_client):
    with patch("src.a_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = ([], 0)
        mock_store.return_value = mock_instance
        resp = authenticated_client.get("/api/v1/a-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
    assert resp.json()["items"] == []


def test_add_watchlist_missing_symbol(authenticated_client):
    resp = authenticated_client.post("/api/v1/a-stock/watchlist", json={"name": "Test"})
    assert resp.status_code == 422


def test_quotes_reuse_polling_cache(authenticated_client):
    routes._quotes_cache.clear()
    frame = pd.DataFrame([{"symbol": "000001.SZ", "close": 10.0}])
    with patch("src.data.providers.akshare_provider._fetch_tencent_quotes_batch", return_value=frame) as fetch:
        first = authenticated_client.post("/api/v1/a-stock/quotes", json=["000001.SZ"])
        second = authenticated_client.post("/api/v1/a-stock/quotes", json=["000001.SZ"])

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert fetch.call_count == 1
