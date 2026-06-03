import pytest
from unittest.mock import MagicMock

from src.a_stock.watchlist import AShareWatchlistStore


@pytest.fixture
def mock_db():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_list_items(mock_db):
    conn, cursor = mock_db
    cursor.fetchall.return_value = [
        {"id": 1, "symbol": "600519.SH", "name": "贵州茅台", "sort_order": 0, "created_at": "2026-01-01"},
    ]
    store = AShareWatchlistStore(conn)
    items = store.list_items()
    assert len(items) == 1
    assert items[0].symbol == "600519.SH"


def test_add_item(mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = {
        "id": 1, "symbol": "600519.SH", "name": "贵州茅台", "sort_order": 0, "created_at": "2026-01-01",
    }
    store = AShareWatchlistStore(conn)
    item = store.add("600519.SH", "贵州茅台")
    assert item.symbol == "600519.SH"


def test_add_duplicate_raises(mock_db):
    conn, cursor = mock_db
    cursor.execute.side_effect = Exception("duplicate key")
    store = AShareWatchlistStore(conn)
    with pytest.raises(ValueError, match="already exists"):
        store.add("600519.SH", "贵州茅台")


def test_remove_item(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 1
    store = AShareWatchlistStore(conn)
    result = store.remove("600519.SH")
    assert result is True


def test_remove_not_found(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 0
    store = AShareWatchlistStore(conn)
    result = store.remove("INVALID")
    assert result is False