from sqlalchemy import create_engine

from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"

def test_runtime_store_persists_alpha_ticket_and_manual_fill(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="discount to reference",
        suggested_quantity=2.0,
        suggested_limit_price=210.5,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.approve_alpha_ticket( ticket_id=ticket_id, operator_id="trader-01")
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
    store = RuntimeStore(engine, TenantContext("test-user"))

    store.replace_alpha_positions(
        positions=[
            {"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0},
            {"symbol": "SPYx", "quantity": 2.0, "avg_cost": 500.0, "mark_price": 504.0},
        ],
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
    store = RuntimeStore(engine, TenantContext("test-user"))

    store.add_alpha_watchlist_item( symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    store.add_alpha_watchlist_item( symbol="SPYx", underlying_symbol="SPY", priority=2)

    items = store.list_alpha_watchlist_items()

    assert [item["symbol"] for item in items] == ["AAPLx", "SPYx"]

    store.remove_alpha_watchlist_item(symbol="SPYx")
    assert [item["symbol"] for item in store.list_alpha_watchlist_items()] == ["AAPLx"]


def test_alpha_watchlist_allows_same_symbol_for_different_users(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    alice = RuntimeStore(engine, TenantContext("alice"))
    bob = RuntimeStore(engine, TenantContext("bob"))

    alice.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    bob.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=2)

    assert alice.list_alpha_watchlist_items()[0]["priority"] == 1
    assert bob.list_alpha_watchlist_items()[0]["priority"] == 2

    alice.remove_alpha_watchlist_item("AAPLx")
    assert alice.list_alpha_watchlist_items() == []
    assert bob.list_alpha_watchlist_items()[0]["symbol"] == "AAPLx"


def test_runtime_store_persists_alpha_api_order_attempt(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

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


def test_runtime_store_manages_alpha_holdings_entries(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    entry_id = store.insert_alpha_holdings_entry(
        symbol="MSFT.US",
        buy_date="2026-06-20",
        buy_price=420.5,
        quantity=2.0,
    )

    entries = store.list_alpha_holdings_entries()
    assert len(entries) == 1
    assert entries[0]["entry_id"] == entry_id
    assert entries[0]["symbol"] == "MSFT.US"
    assert entries[0]["buy_date"] == "2026-06-20"
    assert entries[0]["buy_price"] == 420.5
    assert entries[0]["quantity"] == 2.0

    store.update_alpha_holdings_entry(
        entry_id,
        symbol="MSFT.US",
        buy_date="2026-06-21",
        buy_price=425.0,
        quantity=3.0,
    )
    updated = store.list_alpha_holdings_entries()[0]
    assert updated["buy_date"] == "2026-06-21"
    assert updated["buy_price"] == 425.0
    assert updated["quantity"] == 3.0

    store.delete_alpha_holdings_entry(entry_id)
    assert store.list_alpha_holdings_entries() == []


def test_alpha_holdings_entries_are_user_isolated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    alice = RuntimeStore(engine, TenantContext("alice"))
    bob = RuntimeStore(engine, TenantContext("bob"))

    alice.insert_alpha_holdings_entry(
        symbol="AAPL.US",
        buy_date="2026-06-20",
        buy_price=200.0,
        quantity=1.0,
    )
    bob.insert_alpha_holdings_entry(
        symbol="AAPL.US",
        buy_date="2026-06-21",
        buy_price=210.0,
        quantity=2.0,
    )

    assert len(alice.list_alpha_holdings_entries()) == 1
    assert len(bob.list_alpha_holdings_entries()) == 1
    assert alice.list_alpha_holdings_entries()[0]["buy_price"] == 200.0
    assert bob.list_alpha_holdings_entries()[0]["buy_price"] == 210.0
