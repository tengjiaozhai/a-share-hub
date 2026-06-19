import pytest
from unittest.mock import Mock, MagicMock
from src.use_cases.create_decision_run import (
    CreateDecisionRunUseCase,
    CreateDecisionRunRequest,
    CreateDecisionRunResponse,
)
from src.domain.value_objects.symbol import Symbol
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository

TEST_USER_ID = "test-user"


@pytest.fixture
def repository():
    return InMemoryDecisionRunRepository()


@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.model = "deepseek"
    client.generate.return_value = '{"symbol": "600519.SH", "action": "BUY", "confidence": 80, "target_position_ratio": 0.15, "reason": "Strong signal"}'
    return client


@pytest.fixture
def use_case(repository, mock_llm_client):
    return CreateDecisionRunUseCase(
        decision_run_repository=repository,
        llm_client=mock_llm_client,
    )


def test_create_decision_run_success(use_case, repository):
    """测试成功创建决策运行"""
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
        user_id=TEST_USER_ID,
    )

    response = use_case.execute(request)

    assert response.success is True
    assert response.decision_run_id is not None
    assert response.error is None

    # 验证记录已保存
    record = repository.get_decision_run(user_id=TEST_USER_ID, decision_run_id=response.decision_run_id)
    assert record is not None
    assert record["symbol"] == "600519.SH"
    assert record["parsed_action"] == "BUY"


def test_create_decision_run_with_mock_llm(use_case, repository):
    """测试使用模拟LLM创建决策运行"""
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=True,
        user_id=TEST_USER_ID,
    )

    response = use_case.execute(request)

    assert response.success is True
    assert response.decision_run_id is not None


def test_create_decision_run_llm_failure(repository):
    """测试LLM失败时创建决策运行"""
    mock_llm_client = Mock()
    mock_llm_client.model = "deepseek"
    mock_llm_client.generate.return_value = None

    use_case = CreateDecisionRunUseCase(
        decision_run_repository=repository,
        llm_client=mock_llm_client,
    )

    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
        user_id=TEST_USER_ID,
    )

    response = use_case.execute(request)

    assert response.success is False
    assert response.error == "LLM client returned no output"
    assert response.decision_run_id is None


def test_create_decision_run_invalid_symbol(use_case):
    """测试无效股票代码"""
    with pytest.raises(ValueError, match="无效的股票代码格式"):
        request = CreateDecisionRunRequest(
            symbol=Symbol("invalid"),
            mock_llm=False,
            user_id=TEST_USER_ID,
        )
