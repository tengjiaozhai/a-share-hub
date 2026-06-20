import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.a_stock.watchlist import AShareWatchlistStore
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
    """创建 AShareWatchlistStore 实例"""
    tenant = TenantContext(TEST_USER_ID)
    return AShareWatchlistStore(db_engine, tenant)


def test_list_items_empty(store):
    """测试空列表"""
    items, total = store.list_items()
    assert total == 0
    assert items == []


def test_add_item(store):
    """测试添加项目"""
    item = store.add("600519.SH", "贵州茅台")
    assert item.symbol == "600519.SH"
    assert item.name == "贵州茅台"
    assert item.id > 0


def test_list_items(store):
    """测试列出项目"""
    # 添加两个项目
    store.add("600519.SH", "贵州茅台", sort_order=1)
    store.add("000858.SZ", "五粮液", sort_order=0)
    
    items, total = store.list_items()
    assert total == 2
    assert len(items) == 2
    # 验证按 sort_order 排序
    assert items[0].symbol == "000858.SZ"
    assert items[1].symbol == "600519.SH"


def test_add_duplicate_raises(store):
    """测试添加重复项目抛出异常"""
    store.add("600519.SH", "贵州茅台")
    with pytest.raises(ValueError, match="already exists"):
        store.add("600519.SH", "贵州茅台")


def test_remove_item(store):
    """测试删除项目"""
    store.add("600519.SH", "贵州茅台")
    result = store.remove("600519.SH")
    assert result is True
    
    items, total = store.list_items()
    assert total == 0


def test_remove_not_found(store):
    """测试删除不存在的项目"""
    result = store.remove("INVALID")
    assert result is False


def test_get_by_symbol(store):
    """测试按代码查询"""
    store.add("600519.SH", "贵州茅台")
    item = store.get_by_symbol("600519.SH")
    assert item is not None
    assert item.symbol == "600519.SH"
    assert item.name == "贵州茅台"


def test_get_by_symbol_not_found(store):
    """测试查询不存在的项目"""
    item = store.get_by_symbol("INVALID")
    assert item is None
