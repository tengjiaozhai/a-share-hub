import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.us_stock.watchlist import WatchlistStore
from src.core.tenant import TenantContext
from src.storage.models import Base

TEST_USER_ID = "test-user-1"


@pytest.fixture
def db_engine():
    """创建内存 SQLite 数据库用于测试"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def store(db_engine):
    """创建 WatchlistStore 实例"""
    tenant = TenantContext(TEST_USER_ID)
    return WatchlistStore(db_engine, tenant)


def test_list_items_empty(store):
    """测试空列表"""
    items, total = store.list_items()
    assert total == 0
    assert items == []


def test_add_item(store):
    """测试添加项目"""
    item = store.add("AAPL", "Apple Inc.")
    assert item.symbol == "AAPL"
    assert item.name == "Apple Inc."
    assert item.id > 0


def test_list_items(store):
    """测试列出项目"""
    # 添加两个项目
    store.add("AAPL", "Apple Inc.", sort_order=1)
    store.add("GOOGL", "Alphabet Inc.", sort_order=0)
    
    items, total = store.list_items()
    assert total == 2
    assert len(items) == 2
    # 验证按 sort_order 排序
    assert items[0].symbol == "GOOGL"
    assert items[1].symbol == "AAPL"


def test_add_duplicate_raises(store):
    """测试添加重复项目抛出异常"""
    store.add("AAPL", "Apple Inc.")
    with pytest.raises(ValueError, match="already exists"):
        store.add("AAPL", "Apple Inc.")


def test_remove_item(store):
    """测试删除项目"""
    store.add("AAPL", "Apple Inc.")
    result = store.remove("AAPL")
    assert result is True
    
    items, total = store.list_items()
    assert total == 0


def test_remove_not_found(store):
    """测试删除不存在的项目"""
    result = store.remove("INVALID")
    assert result is False


def test_get_by_symbol(store):
    """测试按代码查询"""
    store.add("AAPL", "Apple Inc.")
    item = store.get_by_symbol("AAPL")
    assert item is not None
    assert item.symbol == "AAPL"
    assert item.name == "Apple Inc."


def test_get_by_symbol_not_found(store):
    """测试查询不存在的项目"""
    item = store.get_by_symbol("INVALID")
    assert item is None
