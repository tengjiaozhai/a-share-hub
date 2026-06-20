from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


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
