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