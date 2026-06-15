import pytest
from unittest.mock import Mock, patch
from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from src.use_cases.handlers.decision_handlers import DecisionEventHandlers


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def handlers(event_bus):
    return DecisionEventHandlers(event_bus)


def test_handlers_subscribe_to_events(event_bus, handlers):
    """测试处理器订阅事件"""
    # 验证处理器订阅了正确的事件
    created_subscribers = event_bus.get_subscribers(DecisionRunCreated)
    failed_subscribers = event_bus.get_subscribers(DecisionRunFailed)
    
    assert len(created_subscribers) == 1
    assert len(failed_subscribers) == 1


def test_handle_decision_run_created(event_bus, handlers):
    """测试处理决策运行创建事件"""
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    # 发布事件
    event_bus.publish(event)
    
    # 验证事件被记录
    published_events = event_bus.get_published_events_by_type(DecisionRunCreated)
    assert len(published_events) == 1
    assert published_events[0] == event


def test_handle_decision_run_failed(event_bus, handlers):
    """测试处理决策运行失败事件"""
    event = DecisionRunFailed(
        decision_run_id="dr-123",
        symbol="600519.SH",
        error="LLM client returned no output",
        model_name="deepseek",
    )
    
    # 发布事件
    event_bus.publish(event)
    
    # 验证事件被记录
    published_events = event_bus.get_published_events_by_type(DecisionRunFailed)
    assert len(published_events) == 1
    assert published_events[0] == event


def test_handlers_registered_correctly(handlers):
    """测试处理器正确注册"""
    handler_dict = handlers.get_handlers()
    
    assert "DecisionRunCreated" in handler_dict
    assert "DecisionRunFailed" in handler_dict
    assert callable(handler_dict["DecisionRunCreated"])
    assert callable(handler_dict["DecisionRunFailed"])
