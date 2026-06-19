from unittest.mock import MagicMock

import pytest

from src.us_stock.watchlist import WatchlistStore


TEST_USER_ID = "test-user-1"


@pytest.fixture
def mock_db():
    """模拟数据库连接，返回 (conn, cursor)。"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_list_items(mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = {"count": 1}
    cursor.fetchall.return_value = [
        {"id": 1, "symbol": "AAPL", "name": "Apple", "sort_order": 0, "created_at": "2026-01-01"},
    ]
    store = WatchlistStore(conn, TEST_USER_ID)
    items, total = store.list_items()
    assert total == 1
    assert len(items) == 1
    assert items[0].symbol == "AAPL"
    list_args = cursor.execute.call_args_list[0][0][1]
    assert TEST_USER_ID in list_args


def test_add_item(mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = {
        "id": 1, "symbol": "AAPL", "name": "Apple", "sort_order": 0, "created_at": "2026-01-01",
    }
    store = WatchlistStore(conn, TEST_USER_ID)
    item = store.add("AAPL", "Apple")
    assert item.symbol == "AAPL"
    insert_args = cursor.execute.call_args[0][1]
    assert TEST_USER_ID in insert_args


def test_add_duplicate_raises(mock_db):
    conn, cursor = mock_db
    cursor.execute.side_effect = Exception("duplicate key")
    store = WatchlistStore(conn, TEST_USER_ID)
    with pytest.raises(ValueError, match="already exists"):
        store.add("AAPL", "Apple")


def test_remove_item(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 1
    store = WatchlistStore(conn, TEST_USER_ID)
    result = store.remove("AAPL")
    assert result is True
    delete_args = cursor.execute.call_args[0][1]
    assert TEST_USER_ID in delete_args


def test_remove_not_found(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 0
    store = WatchlistStore(conn, TEST_USER_ID)
    result = store.remove("INVALID")
    assert result is False
