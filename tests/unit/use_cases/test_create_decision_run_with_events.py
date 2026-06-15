import pytest
from unittest.mock import Mock
from src.use_cases.create_decision_run import (
    CreateDecisionRunUseCase,
    CreateDecisionRunRequest,
    CreateDecisionRunResponse,
)
from src.domain.value_objects.symbol import Symbol
from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
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
def use_case(repository, event_bus, mock_llm_client):
    return CreateDecisionRunUseCase(
        decision_run_repository=repository,
        event_bus=event_bus,
        llm_client=mock_llm_client,
    )


def test_create_decision_run_publishes_success_event(use_case, event_bus):
    """测试创建决策运行发布成功事件"""
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
    )
    
    response = use_case.execute(request)
    
    assert response.success is True
    
    # 验证发布了成功事件
    published_events = event_bus.get_published_events_by_type(DecisionRunCreated)
    assert len(published_events) == 1
    
    event = published_events[0]
    assert event.decision_run_id == response.decision_run_id
    assert event.symbol == "600519.SH"
    assert event.action == "BUY"


def test_create_decision_run_publishes_failure_event(repository, event_bus):
    """测试创建决策运行发布失败事件"""
    mock_llm_client = Mock()
    mock_llm_client.model = "deepseek"
    mock_llm_client.generate.return_value = None
    
    use_case = CreateDecisionRunUseCase(
        decision_run_repository=repository,
        event_bus=event_bus,
        llm_client=mock_llm_client,
    )
    
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
    )
    
    response = use_case.execute(request)
    
    assert response.success is False
    
    # 验证发布了失败事件
    published_events = event_bus.get_published_events_by_type(DecisionRunFailed)
    assert len(published_events) == 1
    
    event = published_events[0]
    assert event.symbol == "600519.SH"
    assert event.error == "LLM client returned no output"


def test_create_decision_run_no_event_bus(repository, mock_llm_client):
    """测试没有事件总线时创建决策运行"""
    use_case = CreateDecisionRunUseCase(
        decision_run_repository=repository,
        event_bus=None,
        llm_client=mock_llm_client,
    )
    
    request = CreateDecisionRunRequest(
        symbol=Symbol("600519.SH"),
        mock_llm=False,
    )
    
    response = use_case.execute(request)
    
    assert response.success is True
    assert response.decision_run_id is not None
