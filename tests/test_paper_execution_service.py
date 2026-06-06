from sqlalchemy import create_engine

from src.execution.paper_execution_service import PaperExecutionService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_paper_execution_service_records_order_fill_and_account_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    result = service.execute_targets(
        targets=[
            {
                "target_position_id": "tp-001",
                "symbol": "600519.SH",
                "action": "BUY",
                "quantity": 100,
                "price": 100.0,
                "notional": 10_000,
            }
        ],
        initial_state={"cash": 1_000_000.0, "positions": {}},
        mark_prices={"600519.SH": 101.0},
        trade_date="2026-06-04",
    )

    orders = store.list_execution_orders(limit=10)
    events = store.list_broker_events(limit=10)
    snapshot = store.get_latest_account_snapshot()

    assert result["status"] == "ok"
    assert orders[0]["status"] == "FILLED"
    assert any(event["event_type"] == "FILLED" for event in events)
    assert snapshot["nav"] > 999_000
