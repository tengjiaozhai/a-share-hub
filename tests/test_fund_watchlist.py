import pytest
from sqlalchemy import create_engine

from src.core.tenant import TenantContext
from src.fund.watchlist import FundWatchlistStore
from src.storage.models import Base


@pytest.fixture
def store():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    try:
        yield FundWatchlistStore(engine, TenantContext("test-user-1"))
    finally:
        engine.dispose()


def test_fund_watchlist_crud(store):
    item = store.add("020972.OTC", "华夏基金")
    assert item.symbol == "020972.OTC"
    assert item.name == "华夏基金"

    items, total = store.list_items()
    assert total == 1
    assert items[0].symbol == "020972.OTC"

    assert store.get_by_symbol("020972.OTC").name == "华夏基金"
    assert store.remove("020972.OTC") is True
    assert store.list_items() == ([], 0)


def test_fund_watchlist_duplicate_raises(store):
    store.add("020972.OTC", "华夏基金")
    with pytest.raises(ValueError, match="already exists"):
        store.add("020972.OTC", "华夏基金")
