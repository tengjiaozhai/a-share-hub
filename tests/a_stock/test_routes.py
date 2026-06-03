from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.main import build_app


client = TestClient(build_app())


def test_get_watchlist():
    with patch("src.a_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = []
        mock_store.return_value = mock_instance
        resp = client.get("/api/v1/a-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_add_watchlist_missing_symbol():
    resp = client.post("/api/v1/a-stock/watchlist", json={"name": "Test"})
    assert resp.status_code == 422
