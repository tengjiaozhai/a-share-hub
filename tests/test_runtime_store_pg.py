from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_ready_plan_in_relational_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    plan_id = store.insert_execution_plan(
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        reason="unit-test",
    )
    plans = store.list_ready_execution_plans()
    assert len(plans) == 1
    assert plans[0]["plan_id"] == plan_id


def test_runtime_store_persists_kill_switch_state(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    store.set_kill_switch(True)
    assert store.get_kill_switch() is True


def test_runtime_store_persists_execution_order_and_broker_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    execution_order_id = store.insert_execution_order(
        target_position_id="tp-001",
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1420.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "qmt-001"},
    )

    status = store.get_reconciliation_status()
    assert status["open_orders"] == 1
    assert status["broker_event_count"] == 1


def test_runtime_store_inserts_kill_switch_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.insert_kill_switch_event(active=True, reason="manual halt")
    store.insert_kill_switch_event(active=False, reason="resume")

    assert store.get_kill_switch() is False


def test_runtime_store_can_mark_execution_order_filled_and_sum_daily_pnl(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    execution_order_id = store.insert_execution_order(
        target_position_id="tp-001",
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=100.0,
    )
    store.update_execution_order_status(execution_order_id, status="FILLED")
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-filled-001",
        event_type="FILLED",
        payload={"pnl_delta": 1250.0, "run_context_id": "wrk-test-001"},
    )

    latest_order = store.list_execution_orders(limit=1)[0]
    assert latest_order["status"] == "FILLED"
    assert store.sum_daily_pnl() == 1250.0
