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