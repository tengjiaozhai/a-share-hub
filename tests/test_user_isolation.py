"""两用户隔离测试：dashboard aggregates / broker events / reconciliation。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.tenant import SYSTEM_TENANT, TenantContext
from src.paper_ledger.models import PaperBase
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.storage.system_runtime_store import SystemRuntimeStore


def _ensure_user(engine, user_id: str) -> None:
    from datetime import datetime
    from sqlalchemy import insert

    from src.storage.auth_models import AppUserRow

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


@pytest.fixture
def two_user_stores(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    PaperBase.metadata.create_all(engine)
    Base.metadata.create_all(engine)
    _ensure_user(engine, "alice")
    _ensure_user(engine, "bob")
    system = SystemRuntimeStore(engine)
    alice = RuntimeStore(engine, TenantContext("alice"))
    bob = RuntimeStore(engine, TenantContext("bob"))
    return alice, bob, system


def _seed_order(store: RuntimeStore, *, run_context_id: str, symbol: str) -> str:
    target_position_id = store.insert_target_position(
        decision_run_id=f"decision-for-{run_context_id}",
        symbol=symbol,
        action="BUY",
        target_value=100,
        target_position_ratio=0.1,
        expires_at="2027-01-01T00:00:00",
        run_context_id=run_context_id,
    )
    return store.insert_execution_order(
        target_position_id=target_position_id,
        run_context_id=run_context_id,
        symbol=symbol,
        action="BUY",
        quantity=10,
        limit_price=150.0,
    )


def test_broker_events_are_tenant_scoped(two_user_stores):
    alice, bob, system = two_user_stores
    alice_order = _seed_order(alice, run_context_id="run-alice", symbol="AAPL")
    bob_order = _seed_order(bob, run_context_id="run-bob", symbol="TSLA")

    system.record_broker_event(
        event_id="event-a1",
        order_id=alice_order,
        event_type="FILLED",
        payload={"pnl_delta": 10.0},
    )
    system.record_broker_event(
        event_id="event-b1",
        order_id=bob_order,
        event_type="FILLED",
        payload={"pnl_delta": -4.0},
    )

    assert [r["event_id"] for r in alice.list_broker_events()] == ["event-a1"]
    assert [r["event_id"] for r in bob.list_broker_events()] == ["event-b1"]


def test_dashboard_pnl_is_tenant_scoped(two_user_stores):
    alice, bob, system = two_user_stores
    alice_order = _seed_order(alice, run_context_id="run-alice", symbol="AAPL")
    bob_order = _seed_order(bob, run_context_id="run-bob", symbol="TSLA")

    system.record_broker_event(
        event_id="alice-event",
        order_id=alice_order,
        event_type="FILLED",
        payload={"pnl_delta": 10.0},
    )
    system.record_broker_event(
        event_id="bob-event",
        order_id=bob_order,
        event_type="FILLED",
        payload={"pnl_delta": -4.0},
    )

    assert alice.sum_daily_pnl() == 10.0
    assert bob.sum_daily_pnl() == -4.0


def test_dashboard_reconciliation_is_tenant_scoped(two_user_stores):
    alice, bob, system = two_user_stores
    alice_order = _seed_order(alice, run_context_id="run-alice", symbol="AAPL")
    bob_order = _seed_order(bob, run_context_id="run-bob", symbol="TSLA")

    system.record_broker_event(
        event_id="alice-event",
        order_id=alice_order,
        event_type="FILLED",
        payload={"pnl_delta": 10.0},
    )
    system.record_broker_event(
        event_id="bob-event",
        order_id=bob_order,
        event_type="FILLED",
        payload={"pnl_delta": -4.0},
    )

    alice_recon = alice.get_reconciliation_status()
    bob_recon = bob.get_reconciliation_status()
    assert alice_recon["broker_event_count"] == 1
    assert bob_recon["broker_event_count"] == 1


def test_dashboard_recent_events_are_tenant_scoped(two_user_stores, monkeypatch):
    from src.api import routes_dashboard

    alice, bob, system = two_user_stores
    alice_order = _seed_order(alice, run_context_id="run-alice", symbol="AAPL")
    bob_order = _seed_order(bob, run_context_id="run-bob", symbol="TSLA")

    system.record_broker_event(
        event_id="alice-event",
        order_id=alice_order,
        event_type="FILLED",
        payload={"pnl_delta": 10.0},
    )
    system.record_broker_event(
        event_id="bob-event",
        order_id=bob_order,
        event_type="FILLED",
        payload={"pnl_delta": -4.0},
    )

    alice_events = routes_dashboard._list_recent_events(alice, limit=10)
    bob_events = routes_dashboard._list_recent_events(bob, limit=10)

    alice_ids = {e.get("event_id") for e in alice_events if e.get("type") == "broker_event"}
    bob_ids = {e.get("event_id") for e in bob_events if e.get("type") == "broker_event"}

    assert "alice-event" in alice_ids
    assert "bob-event" not in alice_ids
    assert "bob-event" in bob_ids
    assert "alice-event" not in bob_ids


def test_system_tenant_does_not_inherit_user_broker_events(two_user_stores):
    """确保 SYSTEM_TENANT 不会误继承任何用户的 broker events。"""
    alice, _bob, system = two_user_stores
    alice_order = _seed_order(alice, run_context_id="run-alice", symbol="AAPL")

    system.record_broker_event(
        event_id="alice-event",
        order_id=alice_order,
        event_type="FILLED",
        payload={"pnl_delta": 10.0},
    )

    system_store = RuntimeStore(two_user_stores[0].engine, SYSTEM_TENANT)
    assert system_store.list_broker_events() == []
    assert system_store.sum_daily_pnl() == 0.0
