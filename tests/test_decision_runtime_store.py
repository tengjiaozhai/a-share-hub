from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"


def test_runtime_store_persists_decision_run_and_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="prompt-v1",
        model_name="mock-llm",
        raw_output='{"symbol":"600519.SH","action":"BUY","confidence":80,"target_position_ratio":0.2,"reason":"trend"}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.2,
        reason="trend",
        input_snapshot={"market": {"symbol": "600519.SH", "close": 1420.0}},
    )

    record = store.get_decision_run(user_id=TEST_USER_ID, decision_run_id=decision_run_id)
    assert record["decision_run_id"] == decision_run_id
    assert record["snapshot"]["market"]["close"] == 1420.0
    assert record["target_position_ratio"] == 0.2


def test_runtime_store_lists_active_target_positions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="prompt-v1",
        model_name="mock-llm",
        raw_output='{"symbol":"600519.SH","action":"BUY","confidence":80,"target_position_ratio":0.2,"reason":"trend"}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.2,
        reason="trend",
        input_snapshot={"market": {"symbol": "600519.SH"}},
    )
    store.insert_target_position(
        user_id=TEST_USER_ID,
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=200000,
        target_position_ratio=0.2,
        expires_at="2026-12-31T10:15:00",
    )

    rows = store.list_active_target_positions(user_id=TEST_USER_ID)
    assert len(rows) == 1
    assert rows[0]["decision_run_id"] == decision_run_id


def test_runtime_store_lists_decision_runs(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="prompt-v1",
        model_name="mock-llm",
        raw_output='{"action":"BUY"}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.2,
        reason="trend",
        input_snapshot={},
    )
    store.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="000001.SZ",
        prompt_hash="prompt-v2",
        model_name="mock-llm",
        raw_output='{"action":"SELL"}',
        parsed_action="SELL",
        confidence=60,
        target_position_ratio=0.0,
        reason="weak",
        input_snapshot={},
    )

    rows = store.list_decision_runs(user_id=TEST_USER_ID)
    assert len(rows) == 2
