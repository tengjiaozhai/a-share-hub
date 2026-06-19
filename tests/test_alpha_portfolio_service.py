from sqlalchemy import create_engine

from src.alpha.portfolio_service import AlphaPortfolioService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"


def test_portfolio_service_rebuilds_positions_from_manual_fills(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        user_id=TEST_USER_ID,
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="phase2 seed",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        user_id=TEST_USER_ID,
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )

    service = AlphaPortfolioService(store, user_id=TEST_USER_ID)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0},
        ticket_lookup={ticket_id: {"asset_symbol": "AAPLx", "action": "BUY"}},
    )

    assert round(summary["cash_balance"], 2) == 9_600.0
    assert round(summary["unrealized_pnl"], 2) == 20.0
    assert round(summary["nav"], 2) == 10_020.0
    assert summary["positions"][0]["symbol"] == "AAPLx"


def test_portfolio_service_loads_enriched_fill_history(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        user_id=TEST_USER_ID,
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="phase2 seed",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        user_id=TEST_USER_ID,
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        executed_at="2026-06-01T10:30:00+08:00",
        notes="buy fill",
    )
    store.replace_alpha_positions(
        user_id=TEST_USER_ID,
        positions=[{"symbol": "AAPLx", "quantity": 2.0, "avg_cost": 200.0, "mark_price": 210.0}],
    )
    store.insert_alpha_portfolio_snapshot(
        user_id=TEST_USER_ID,
        cash_balance=9_600.0,
        realized_pnl=0.0,
        unrealized_pnl=20.0,
        nav=10_020.0,
    )

    service = AlphaPortfolioService(store, user_id=TEST_USER_ID)
    portfolio = service.load_portfolio()

    assert portfolio["snapshot"]["nav"] == 10_020.0
    assert portfolio["positions"][0]["symbol"] == "AAPLx"
    assert portfolio["fills"][0]["ticket_id"] == ticket_id
    assert portfolio["fills"][0]["asset_symbol"] == "AAPLx"
    assert portfolio["fills"][0]["action"] == "BUY"
    assert portfolio["fills"][0]["executed_at"] == "2026-06-01T10:30:00+08:00"
