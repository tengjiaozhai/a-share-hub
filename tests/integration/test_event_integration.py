import pytest
from unittest.mock import Mock
from src.use_cases.create_decision_run import (
    CreateDecisionRunUseCase,
    CreateDecisionRunRequest,
)
from src.domain.value_objects.symbol import Symbol
from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from src.use_cases.handlers.decision_handlers import DecisionEventHandlers
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository


@pytest.fixture
def repository():
    return InMemoryDecisionRunRepository()


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.model = "deepseek"
    client.generate.return_value = '{"symbol": "600519.SH", "action": "BUY", "confidence": 80, "target_position_ratio": 0.15, "reason": "Strong signal"}'
    return client


@pytest.fixture
def setup_handlers(event_bus):
    """设置事件处理器"""
    return DecisionEventHandlers(event_bus)


def test_end_to_end_decision_creation_with_events(repository, event_bus, mock_llm_client, setup_handlers):
    """端到端测试决策创建和事件处理"""
    # 创建用例
    use_case = CreateDecisionRunUseCase(
        decision_run_repository=repository,
        event_bus=event_bus,
        llm_client=mock_llm_client,
    )
    
    # 创建请求
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
    )
    
    # 执行用例
    response = use_case.execute(request)
    
    # 验证成功
    assert response.success is True
    assert response.decision_run_id is not None
    
    # 验证记录已保存
    record = repository.get_decision_run(response.decision_run_id)
    assert record is not None
    assert record["symbol"] == "600519.SH"
    
    # 验证事件已发布
    published_events = event_bus.get_published_events_by_type(DecisionRunCreated)
    assert len(published_events) == 1
    
    event = published_events[0]
    assert event.decision_run_id == response.decision_run_id
    assert event.symbol == "600519.SH"
    assert event.action == "BUY"


def test_end_to_end_decision_failure_with_events(repository, event_bus, setup_handlers):
    """端到端测试决策失败和事件处理"""
    # 创建模拟失败的LLM客户端
    mock_llm_client = Mock()
    mock_llm_client.model = "deepseek"
    mock_llm_client.generate.return_value = None
    
    # 创建用例
    use_case = CreateDecisionRunUseCase(
        decision_run_repository=repository,
        event_bus=event_bus,
        llm_client=mock_llm_client,
    )
    
    # 创建请求
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
    )
    
    # 执行用例
    response = use_case.execute(request)
    
    # 验证失败
    assert response.success is False
    assert response.error == "LLM client returned no output"
    
    # 验证事件已发布
    published_events = event_bus.get_published_events_by_type(DecisionRunFailed)
    assert len(published_events) == 1
    
    event = published_events[0]
    assert event.symbol == "600519.SH"
    assert event.error == "LLM client returned no output"
