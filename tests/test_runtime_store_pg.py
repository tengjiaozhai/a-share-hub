from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_lists_run_scoped_target_order_and_snapshot_details(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="dashboard-wrk-001",
        run_context_id="wrk-001",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="seed decision",
        input_snapshot={"symbol": "600519.SH"},
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        run_context_id="wrk-001",
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        target_position_ratio=0.1,
        expires_at="2026-12-31T10:15:00",
        status="BLOCKED",
        status_reason="cash",
        price=102.5,
        lot_size=100,
        requested_quantity=975.61,
        notional=92250,
        diagnostics={"available_cash": 50000.0, "raw_quantity": 975.61},
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        run_context_id="wrk-001",
        symbol="600519.SH",
        action="BUY",
        quantity=900,
        limit_price=102.5,
        status="PARTIAL",
        status_code="PARTIALLY_FILLED",
        status_reason="first_fill",
        submitted_at="2026-06-14T10:00:00+08:00",
        slippage_bps=5.0,
    )
    store.update_execution_order_status(
        execution_order_id,
        status="PARTIAL",
        status_code="PARTIALLY_FILLED",
        status_reason="400/900 filled",
        filled_quantity=400,
        fill_price=102.55,
        fee=12.31,
        pnl_delta=0.0,
        last_event_at="2026-06-14T10:00:02+08:00",
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        run_context_id="wrk-001",
        event_id="evt-001",
        event_type="PARTIALLY_FILLED",
        payload={"filled_quantity": 400},
    )
    store.insert_account_snapshot(
        cash=950000.0,
        nav=990500.0,
        run_context_id="wrk-001",
        positions={
            "600519.SH": {
                "quantity": 400,
                "avg_cost": 102.55,
                "mark_price": 103.10,
                "market_value": 41240.0,
                "unrealized_pnl": 220.0,
                "change_pct": 0.0054,
                "mark_time": "2026-06-14T10:00:03+08:00",
            }
        },
    )

    targets = store.list_target_positions(run_context_id="wrk-001")
    orders = store.list_execution_orders(run_context_id="wrk-001")
    reconcile = store.get_reconciliation_status(run_context_id="wrk-001")

    assert targets[0]["status_reason"] == "cash"
    assert targets[0]["diagnostics"]["available_cash"] == 50000.0
    assert orders[0]["status_code"] == "PARTIALLY_FILLED"
    assert orders[0]["filled_quantity"] == 400
    assert reconcile["items"][0]["mark_price"] == 103.10
