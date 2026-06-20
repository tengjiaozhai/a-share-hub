import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import insert

from src.api.routes_broker_events import receive_broker_event
from src.core.config import Settings
from src.core.tenant import TenantContext
from src.storage.auth_models import AppUserRow
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.storage.system_runtime_store import SystemRuntimeStore


def _seed_user(engine, user_id: str) -> None:
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


def _seed_order(engine, user_id: str, run_context_id: str) -> str:
    """Insert target_position + execution_order for user_id. Return execution_order_id."""
    store = RuntimeStore(engine, TenantContext(user_id))
    target_position_id = store.insert_target_position(
        decision_run_id="decision-for-broker-event-api",
        symbol="AAPL",
        action="BUY",
        target_value=100,
        target_position_ratio=0.1,
        expires_at="2027-01-01T00:00:00",
        run_context_id=run_context_id,
    )
    return store.insert_execution_order(
        target_position_id=target_position_id,
        run_context_id=run_context_id,
        symbol="AAPL",
        action="BUY",
        quantity=10,
        limit_price=150.0,
    )


def _signed_body(secret: str, body_bytes: bytes, ts: str) -> dict:
    import hashlib
    import hmac

    signature = hmac.new(
        secret.encode(), f"{ts}.".encode() + body_bytes, hashlib.sha256
    ).hexdigest()
    return {"signature": signature, "timestamp": ts, "body": body_bytes}


@pytest.fixture
def hmac_settings(monkeypatch):
    import time

    secret = "test-broker-secret-0001"
    monkeypatch.setenv("BROKER_HMAC_SECRET", secret)
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-auth-secret")
    monkeypatch.setenv("AUTH_SESSION_HOURS", "168")
    settings = Settings()
    settings._test_timestamp = str(int(time.time()))  # noqa: SLF001 - test-only helper
    return settings


def _now_ts() -> str:
    import time

    return str(int(time.time()))


def test_receive_broker_event_inserts_under_owner_tenant(pg_engine, hmac_settings, monkeypatch):
    _seed_user(pg_engine, "alice")
    order_id = _seed_order(pg_engine, "alice", "run-alice")

    body_bytes = json.dumps(
        {
            "event_id": "evt-api-1",
            "event_type": "FILLED",
            "order_id": order_id,
            "fill_price": 152.5,
            "filled_quantity": 10,
            "pnl_delta": 5.0,
        }
    ).encode()
    signed = _signed_body(hmac_settings.broker_hmac_secret, body_bytes, _now_ts())

    class FakeRequest:
        async def body(self):
            return signed["body"]

    import asyncio

    system_store = SystemRuntimeStore(pg_engine)
    result = asyncio.run(
        receive_broker_event(
            request=FakeRequest(),
            store=system_store,
            x_broker_signature=signed["signature"],
            x_broker_timestamp=signed["timestamp"],
        )
    )
    assert result["received"] is True
    assert result["user_id"] == "alice"

    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    events = alice.list_broker_events()
    assert len(events) == 1
    assert events[0]["event_id"] == "evt-api-1"


def test_receive_broker_event_unknown_order_returns_404(pg_engine, hmac_settings, monkeypatch):
    _seed_user(pg_engine, "alice")

    body_bytes = json.dumps(
        {"event_id": "evt-404", "event_type": "FILLED", "order_id": "missing"}
    ).encode()
    signed = _signed_body(hmac_settings.broker_hmac_secret, body_bytes, _now_ts())

    class FakeRequest:
        async def body(self):
            return signed["body"]

    import asyncio

    system_store = SystemRuntimeStore(pg_engine)

    async def _call():
        return await receive_broker_event(
            request=FakeRequest(),
            store=system_store,
            x_broker_signature=signed["signature"],
            x_broker_timestamp=signed["timestamp"],
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_call())

    assert exc_info.value.status_code == 404
    assert "execution order not found" in exc_info.value.detail


def test_receive_broker_event_payload_user_id_is_ignored(pg_engine, hmac_settings, monkeypatch):
    _seed_user(pg_engine, "alice")
    order_id = _seed_order(pg_engine, "alice", "run-alice")

    body_bytes = json.dumps(
        {
            "event_id": "evt-spoof",
            "event_type": "FILLED",
            "order_id": order_id,
            "user_id": "mallory",
            "pnl_delta": 1.0,
        }
    ).encode()
    signed = _signed_body(hmac_settings.broker_hmac_secret, body_bytes, _now_ts())

    class FakeRequest:
        async def body(self):
            return signed["body"]

    import asyncio

    system_store = SystemRuntimeStore(pg_engine)
    result = asyncio.run(
        receive_broker_event(
            request=FakeRequest(),
            store=system_store,
            x_broker_signature=signed["signature"],
            x_broker_timestamp=signed["timestamp"],
        )
    )
    assert result["user_id"] == "alice"

    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    events = alice.list_broker_events()
    assert events[0]["payload"].get("user_id") is None
    assert events[0]["payload"]["pnl_delta"] == 1.0
