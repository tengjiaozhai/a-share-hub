from sqlalchemy import create_engine

from src.alpha.portfolio_service import AlphaPortfolioService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_portfolio_service_rebuilds_positions_from_manual_fills(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="phase2 seed",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0},
        ticket_lookup={ticket_id: {"asset_symbol": "AAPLx", "action": "BUY"}},
    )

    assert round(summary["cash_balance"], 2) == 9_600.0
    assert round(summary["unrealized_pnl"], 2) == 20.0
    assert round(summary["nav"], 2) == 10_020.0
    assert summary["positions"][0]["symbol"] == "AAPLx"
