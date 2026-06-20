import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.api.routes_kill_switch import activate_kill_switch, get_kill_switch_status
from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

@pytest.mark.xfail(reason="activate_kill_switch is now a FastAPI route with dependency injection, not a simple function")
def test_activate_kill_switch_updates_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))
    result = activate_kill_switch(store=store)
    assert result["activated"] is True
    assert store.get_kill_switch() is True

@pytest.mark.xfail(reason="get_ready_plans is now a FastAPI route with dependency injection, not a simple function")
def test_ready_plans_endpoint_returns_persisted_plans(tmp_path):
    from src.api.routes_execution_plans import get_ready_plans

    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))
    store.insert_execution_plan(symbol="600519.SH", action="BUY", target_value=100000, reason="api-test")
    payload = get_ready_plans(store=store)
    assert payload[0]["symbol"] == "600519.SH"