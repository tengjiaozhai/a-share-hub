"""Tests for read-time auto-refresh of mark prices in load_portfolio()."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy import create_engine

from src.alpha.market_price_service import AlphaMarketPriceService, find_stale_symbols, is_stale
from src.alpha.portfolio_service import AlphaPortfolioService
from src.core.tenant import TenantContext
from src.storage.models import AlphaPositionRow, Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"


def _make_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    return RuntimeStore(engine, TenantContext(TEST_USER_ID))


def _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0, backdate_seconds=0):
    store.replace_alpha_positions(
        [{"symbol": symbol, "quantity": quantity, "avg_cost": avg_cost, "mark_price": mark_price}]
    )
    store.insert_alpha_portfolio_snapshot(cash_balance=0.0, realized_pnl=0.0, unrealized_pnl=100.0, nav=2100.0)
    if backdate_seconds > 0:
        old_time = datetime.utcnow() - timedelta(seconds=backdate_seconds)
        with store.engine.begin() as conn:
            conn.execute(
                AlphaPositionRow.__table__.update()
                .where(AlphaPositionRow.user_id == TEST_USER_ID)
                .where(AlphaPositionRow.symbol == symbol)
                .values(updated_at=old_time)
            )


def _mock_price_service(price_map: dict[str, float]) -> AlphaMarketPriceService:
    svc = MagicMock(spec=AlphaMarketPriceService)
    svc.latest_closes.return_value = price_map
    return svc


# ── find_stale_symbols / is_stale ──────────────────────────────────────────────


def test_find_stale_when_updated_at_is_none():
    positions = [{"symbol": "AAPLx", "mark_price": 200.0, "updated_at": None}]
    assert find_stale_symbols(positions) == ["AAPLx"]


def test_find_stale_when_mark_price_zero():
    positions = [{"symbol": "AAPLx", "mark_price": 0.0, "updated_at": datetime.utcnow().isoformat()}]
    assert find_stale_symbols(positions) == ["AAPLx"]


def test_find_stale_when_expired():
    old = (datetime.utcnow() - timedelta(seconds=600)).isoformat()
    positions = [{"symbol": "AAPLx", "mark_price": 200.0, "updated_at": old}]
    assert find_stale_symbols(positions, ttl_seconds=300) == ["AAPLx"]


def test_not_stale_when_fresh():
    recent = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
    positions = [{"symbol": "AAPLx", "mark_price": 200.0, "updated_at": recent}]
    assert find_stale_symbols(positions, ttl_seconds=300) == []


def test_is_stale_returns_true_when_none():
    assert is_stale(None) is True


def test_is_stale_returns_true_when_expired():
    old = (datetime.utcnow() - timedelta(seconds=600)).isoformat()
    assert is_stale(old, ttl_seconds=300) is True


def test_is_stale_returns_false_when_fresh():
    recent = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
    assert is_stale(recent, ttl_seconds=300) is False


# ── load_portfolio auto-refresh ────────────────────────────────────────────────


def test_load_portfolio_refreshes_stale_mark_prices(tmp_path):
    store = _make_store(tmp_path)
    _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0, backdate_seconds=600)

    mock_svc = _mock_price_service({"AAPLx": 250.0})
    service = AlphaPortfolioService(store)
    result = service.load_portfolio(price_service=mock_svc, price_ttl_seconds=300)

    mock_svc.latest_closes.assert_called_once_with(["AAPLx"])
    pos = next(p for p in result["positions"] if p["symbol"] == "AAPLx")
    assert pos["mark_price"] == 250.0
    assert pos["unrealized_pnl"] == (250.0 - 200.0) * 10.0
    assert pos["price_stale"] is False


def test_load_portfolio_does_not_refresh_fresh_positions(tmp_path):
    store = _make_store(tmp_path)
    _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0)

    mock_svc = _mock_price_service({"AAPLx": 250.0})
    service = AlphaPortfolioService(store)
    result = service.load_portfolio(price_service=mock_svc, price_ttl_seconds=300)

    mock_svc.latest_closes.assert_not_called()
    pos = next(p for p in result["positions"] if p["symbol"] == "AAPLx")
    assert pos["mark_price"] == 210.0
    assert pos["price_stale"] is False


def test_load_portfolio_keeps_old_price_when_refresh_fails(tmp_path):
    store = _make_store(tmp_path)
    _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0, backdate_seconds=600)

    mock_svc = _mock_price_service({})
    service = AlphaPortfolioService(store)
    result = service.load_portfolio(price_service=mock_svc, price_ttl_seconds=300)

    mock_svc.latest_closes.assert_called_once_with(["AAPLx"])
    pos = next(p for p in result["positions"] if p["symbol"] == "AAPLx")
    assert pos["mark_price"] == 210.0
    assert pos["price_stale"] is True


def test_load_portfolio_no_refresh_when_disabled(tmp_path):
    store = _make_store(tmp_path)
    _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0, backdate_seconds=600)

    mock_svc = _mock_price_service({"AAPLx": 250.0})
    service = AlphaPortfolioService(store)
    result = service.load_portfolio(auto_refresh_prices=False, price_service=mock_svc)

    mock_svc.latest_closes.assert_not_called()
    pos = next(p for p in result["positions"] if p["symbol"] == "AAPLx")
    assert pos["mark_price"] == 210.0
    assert pos["price_stale"] is True


# ── update_alpha_position_mark_prices ──────────────────────────────────────────


def test_update_alpha_position_mark_prices_only_updates_price(tmp_path):
    store = _make_store(tmp_path)
    _seed_position(store, symbol="AAPLx", quantity=10.0, avg_cost=200.0, mark_price=210.0)

    store.update_alpha_position_mark_prices({"AAPLx": 250.0})

    positions = store.list_alpha_positions()
    pos = next(p for p in positions if p["symbol"] == "AAPLx")
    assert pos["mark_price"] == 250.0
    assert pos["quantity"] == 10.0
    assert pos["avg_cost"] == 200.0
