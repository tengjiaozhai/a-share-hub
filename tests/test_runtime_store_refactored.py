import pytest
from sqlalchemy import create_engine
from src.storage.runtime_store_v2 import RuntimeStoreV2
from src.storage.models import Base

TEST_USER_ID = "test-user"


@pytest.fixture
def engine(tmp_path):
    database_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def store(engine):
    return RuntimeStoreV2(engine)


def test_insert_and_get_decision_run(store):
    """测试插入和获取决策运行记录"""
    decision_run_id = store.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="abc123",
        model_name="deepseek",
        raw_output='{"action": "BUY"}',
        parsed_action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        input_snapshot={},
    )

    assert decision_run_id is not None

    record = store.get_decision_run(user_id=TEST_USER_ID, decision_run_id=decision_run_id)
    assert record is not None
    assert record["symbol"] == "600519.SH"


def test_list_decision_runs(store):
    """测试列出决策运行记录"""
    for i in range(3):
        store.insert_decision_run(
            user_id=TEST_USER_ID,
            symbol=f"60051{i}.SH",
            prompt_hash=f"hash{i}",
            model_name="deepseek",
            raw_output=f'{{"action": "BUY"}}',
            parsed_action="BUY",
            confidence=0.8,
            target_position_ratio=0.15,
            reason="Signal",
            input_snapshot={},
        )

    records = store.list_decision_runs(user_id=TEST_USER_ID)
    assert len(records) == 3
