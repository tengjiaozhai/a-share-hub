import pytest
from sqlalchemy import insert

from src.core.tenant import TenantContext
from src.storage.auth_models import AppUserRow
from src.storage.runtime_store import RuntimeStore
from src.storage.system_runtime_store import SystemRuntimeStore


def _ensure_user(engine, user_id: str) -> None:
    from datetime import datetime

    with engine.begin() as conn:
        conn.execute(
            insert(AppUserRow.__table__).values(
                user_id=user_id,
                username=user_id,
                email=f"{user_id}@test.local",
                password_hash="test-hash",
                role="user",
                disabled=False,
                created_at=datetime.utcnow(),
                last_login_at=datetime.utcnow(),
            )
        )


def insert_test_order(store: RuntimeStore, *, run_context_id: str) -> str:
    """Insert a target_position + execution_order owned by `store.user_id`. Return the execution_order_id."""
    target_position_id = store.insert_target_position(
        decision_run_id="decision-for-test-order",
        symbol="AAPL",
        action="BUY",
        target_value=100,
        target_position_ratio=0.1,
        expires_at="2027-01-01T00:00:00",
        run_context_id=run_context_id,
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        run_context_id=run_context_id,
        symbol="AAPL",
        action="BUY",
        quantity=10,
        limit_price=150.0,
    )
    return execution_order_id


def test_broker_event_derives_user_from_order(pg_engine):
    _ensure_user(pg_engine, "alice")
    _ensure_user(pg_engine, "bob")
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    bob = RuntimeStore(pg_engine, TenantContext("bob"))
    system = SystemRuntimeStore(pg_engine)
    order_id = insert_test_order(alice, run_context_id="run-alice")

    system.record_broker_event(
        event_id="event-1",
        order_id=order_id,
        event_type="FILLED",
        payload={"user_id": "bob", "pnl_delta": 12.5},
    )

    assert alice.list_broker_events()[0]["event_id"] == "event-1"
    assert bob.list_broker_events() == []


def test_broker_event_rejects_unknown_order(pg_engine):
    _ensure_user(pg_engine, "alice")
    system = SystemRuntimeStore(pg_engine)

    with pytest.raises(LookupError, match="execution order not found"):
        system.record_broker_event("event-1", "missing", "FILLED", {})


def test_broker_event_resolves_via_broker_order_id(pg_engine):
    _ensure_user(pg_engine, "alice")
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    system = SystemRuntimeStore(pg_engine)
    order_id = insert_test_order(alice, run_context_id="run-alice")
    alice.update_execution_order_status(
        execution_order_id=order_id,
        status="SUBMITTED",
        broker_order_id="broker-123",
        status_code="SUBMITTED",
        status_reason="submitted",
    )

    system.record_broker_event(
        event_id="event-via-broker",
        order_id="broker-123",
        event_type="FILLED",
        payload={"pnl_delta": 7.0},
    )

    assert alice.list_broker_events()[0]["event_id"] == "event-via-broker"


def test_broker_event_strips_payload_user_id(pg_engine):
    _ensure_user(pg_engine, "alice")
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    system = SystemRuntimeStore(pg_engine)
    order_id = insert_test_order(alice, run_context_id="run-alice")

    system.record_broker_event(
        event_id="event-strip",
        order_id=order_id,
        event_type="FILLED",
        payload={"user_id": "mallory", "pnl_delta": 1.0},
    )

    event = alice.list_broker_events()[0]
    assert "user_id" not in event["payload"]
    assert event["payload"]["pnl_delta"] == 1.0
