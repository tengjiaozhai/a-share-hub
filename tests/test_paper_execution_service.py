from sqlalchemy import create_engine

from src.execution.paper_execution_service import PaperExecutionService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_paper_execution_service_records_reconcile_snapshot_fields(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    service.execute_targets(
        targets=[
            {
                "run_context_id": "wrk-001",
                "target_position_id": "tp-001",
                "symbol": "NVDA",
                "action": "BUY",
                "quantity": 4,
                "price": 100.0,
                "notional": 400,
            }
        ],
        initial_state={"cash": 10_000.0, "positions": {}},
        mark_prices={"NVDA": 99.90},
        quote_meta_by_symbol={"NVDA": {"as_of": "2026-06-15T20:15:06+08:00", "status": "ok"}},
        trade_date="2026-06-15",
    )

    snapshot = store.get_latest_account_snapshot(run_context_id="wrk-001")
    position = snapshot["positions"]["NVDA"]

    assert position["mark_price"] == 99.90
    assert position["market_value"] == 399.6
    assert position["unrealized_pnl"] < 0
    assert position["mark_time"] == "2026-06-15T20:15:06+08:00"


def test_paper_execution_service_records_lifecycle_and_reconcile_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    result = service.execute_targets(
        targets=[
            {
                "run_context_id": "wrk-001",
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
        quote_meta_by_symbol={
            "600519.SH": {
                "price": 101.0,
                "as_of": "2026-06-14T10:00:03+08:00",
                "status": "ok",
            }
        },
        trade_date="2026-06-14",
    )

    order = store.list_execution_orders(run_context_id="wrk-001", limit=1)[0]
    snapshot = store.get_latest_account_snapshot(run_context_id="wrk-001")

    assert result["status"] == "ok"
    assert order["status_code"] == "FILLED"
    assert order["filled_quantity"] == 100
    assert order["submitted_at"] is not None
    assert order["filled_at"] is not None
    assert snapshot["positions"]["600519.SH"]["mark_price"] == 101.0
    assert snapshot["positions"]["600519.SH"]["unrealized_pnl"] > 0
