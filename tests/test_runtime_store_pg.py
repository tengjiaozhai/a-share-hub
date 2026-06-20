from sqlalchemy import create_engine

from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"

def test_runtime_store_lists_run_scoped_target_order_and_snapshot_details(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

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
        execution_order_id=execution_order_id,
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

    targets = store.list_target_positions()
    orders = store.list_execution_orders()
    reconcile = store.get_reconciliation_status()

    assert targets[0]["status_reason"] == "cash"
    assert targets[0]["diagnostics"]["available_cash"] == 50000.0
    assert orders[0]["status_code"] == "PARTIALLY_FILLED"
    assert orders[0]["filled_quantity"] == 400
    assert reconcile["items"][0]["mark_price"] == 103.10

def test_runtime_store_persists_dashboard_run_summary_and_event_log(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    store.upsert_dashboard_run_summary(
        run_context_id="wrk-001",
        trade_date="2026-06-15",
        decision_mode="real",
        execution_mode="full",
        capital_base=10_000,
        status="running",
        execution_fee_total=0.12,
        realized_pnl=0.0,
        unrealized_pnl=-0.48,
        net_pnl=-0.60,
        started_at="2026-06-15T20:15:06+08:00",
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": "wrk-001"}},
    )
    first_seq = store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "请求已受理"},
    )
    second_seq = store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="stage.updated",
        stage="decision",
        status="done",
        payload={"items": [{"symbol": "NVDA", "action": "BUY"}]},
    )

    summary = store.get_dashboard_run_summary(run_context_id="wrk-001")
    events = store.list_dashboard_run_events(run_context_id="wrk-001")

    assert summary["execution_fee_total"] == 0.12
    assert summary["net_pnl"] == -0.60
    assert summary["latest_workbench"]["latest_run"]["run_context_id"] == "wrk-001"
    assert [event["seq"] for event in events] == [first_seq, second_seq]
    assert events[1]["payload"]["items"][0]["symbol"] == "NVDA"

def test_runtime_store_resolves_dashboard_run_market_from_persisted_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    store.insert_decision_run(
        symbol="AAPL",
        prompt_hash="wrk-market-001",
        run_context_id="wrk-market-001",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="seed market",
        input_snapshot={
            "features": {"watchlist": ["AAPL"]},
            "market_context": {"market": "us"},
        },
    )

    assert store.get_dashboard_run_market("wrk-market-001") == "us"

def test_runtime_store_preserves_summary_market_when_later_updates_omit_it(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    store.upsert_dashboard_run_summary(
        run_context_id="wrk-market-preserve",
        trade_date="2026-06-20",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=10_000,
        status="accepted",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at="2026-06-20T09:30:00+08:00",
        finished_at=None,
        latest_workbench={"market": "us", "latest_run": {"run_context_id": "wrk-market-preserve"}},
    )
    store.upsert_dashboard_run_summary(
        run_context_id="wrk-market-preserve",
        trade_date="2026-06-20",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=10_000,
        status="failed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at="2026-06-20T09:30:00+08:00",
        finished_at="2026-06-20T09:31:00+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-market-preserve", "error_message": "failed early"}},
    )

    summary = store.get_dashboard_run_summary("wrk-market-preserve")

    assert summary["latest_workbench"]["market"] == "us"
    assert store.get_dashboard_run_market("wrk-market-preserve", summary["latest_workbench"]) == "us"
