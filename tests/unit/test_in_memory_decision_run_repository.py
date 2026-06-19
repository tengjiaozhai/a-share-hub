import pytest
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository

TEST_USER_ID = "test-user"


@pytest.fixture
def repository():
    return InMemoryDecisionRunRepository()


def test_insert_and_get_decision_run(repository):
    """测试插入和获取决策运行记录"""
    decision_run_id = repository.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="abc123",
        model_name="deepseek",
        raw_output='{"action": "BUY"}',
        parsed_action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        input_snapshot={"features": {"momentum": 0.5}},
    )

    assert decision_run_id is not None
    assert decision_run_id.startswith("dr-")

    record = repository.get_decision_run(user_id=TEST_USER_ID, decision_run_id=decision_run_id)
    assert record is not None
    assert record["symbol"] == "600519.SH"
    assert record["parsed_action"] == "BUY"


def test_list_decision_runs(repository):
    """测试列出决策运行记录"""
    for i in range(3):
        repository.insert_decision_run(
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

    records = repository.list_decision_runs(user_id=TEST_USER_ID)
    assert len(records) == 3


def test_delete_decision_run(repository):
    """测试删除决策运行记录"""
    decision_run_id = repository.insert_decision_run(
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

    assert repository.delete_decision_run(user_id=TEST_USER_ID, decision_run_id=decision_run_id) is True
    assert repository.get_decision_run(user_id=TEST_USER_ID, decision_run_id=decision_run_id) is None


def test_delete_nonexistent_decision_run(repository):
    """测试删除不存在的决策运行记录"""
    assert repository.delete_decision_run(user_id=TEST_USER_ID, decision_run_id="nonexistent") is False
