from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_alpha_ticket_and_manual_fill(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="discount to reference",
        suggested_quantity=2.0,
        suggested_limit_price=210.5,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.approve_alpha_ticket(ticket_id=ticket_id, operator_id="trader-01")
    fill_id = store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=210.2,
        notes="filled manually in app",
    )

    tickets = store.list_alpha_tickets()
    fills = store.list_alpha_manual_fills(ticket_id=ticket_id)

    assert tickets[0]["ticket_id"] == ticket_id
    assert tickets[0]["status"] == "APPROVED"
    assert fills[0]["fill_id"] == fill_id
    assert fills[0]["executed_price"] == 210.2


def test_runtime_store_persists_alpha_portfolio_and_reconciliation_records(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.replace_alpha_positions(
        [
            {"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0},
            {"symbol": "SPYx", "quantity": 2.0, "avg_cost": 500.0, "mark_price": 504.0},
        ]
    )
    snapshot_id = store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=36.8,
        nav=10_314.8,
    )
    run_id = store.insert_alpha_reconciliation_run(
        source="manual",
        status="MISMATCH",
        discrepancies={"AAPLx": {"internal": 1.2, "external": 1.0}},
    )

    positions = store.list_alpha_positions()
    snapshot = store.get_latest_alpha_portfolio_snapshot()
    runs = store.list_alpha_reconciliation_runs()

    assert len(positions) == 2
    assert positions[0]["symbol"] in {"AAPLx", "SPYx"}
    assert snapshot is not None
    assert snapshot["snapshot_id"] == snapshot_id
    assert snapshot["nav"] == 10_314.8
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "MISMATCH"


def test_runtime_store_manages_alpha_watchlist_items(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    store.add_alpha_watchlist_item(symbol="SPYx", underlying_symbol="SPY", priority=2)

    items = store.list_alpha_watchlist_items()

    assert [item["symbol"] for item in items] == ["AAPLx", "SPYx"]

    store.remove_alpha_watchlist_item(symbol="SPYx")
    assert [item["symbol"] for item in store.list_alpha_watchlist_items()] == ["AAPLx"]


def test_runtime_store_persists_alpha_api_order_attempt(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    attempt_id = store.insert_alpha_api_order_attempt(
        ticket_id="alpha-ticket-001",
        asset_symbol="AAPLx",
        action="BUY",
        quantity=1.0,
        limit_price=210.0,
        mode="api",
        status="SUBMITTED",
        remote_order_id="remote-001",
        response_payload={"status": "SUBMITTED"},
    )

    attempts = store.list_alpha_api_order_attempts()

    assert attempts[0]["attempt_id"] == attempt_id
    assert attempts[0]["remote_order_id"] == "remote-001"
    assert attempts[0]["status"] == "SUBMITTED"
