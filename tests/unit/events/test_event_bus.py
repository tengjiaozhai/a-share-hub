import pytest
from unittest.mock import Mock
from src.domain.events.decision_events import DecisionRunCreated
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


def test_publish_event(event_bus):
    """测试发布事件"""
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event)
    
    published_events = event_bus.get_published_events()
    assert len(published_events) == 1
    assert published_events[0] == event


def test_subscribe_and_publish(event_bus):
    """测试订阅和发布"""
    handler = Mock()
    event_bus.subscribe(DecisionRunCreated, handler)
    
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event)
    
    handler.assert_called_once_with(event)


def test_multiple_subscribers(event_bus):
    """测试多个订阅者"""
    handler1 = Mock()
    handler2 = Mock()
    
    event_bus.subscribe(DecisionRunCreated, handler1)
    event_bus.subscribe(DecisionRunCreated, handler2)
    
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event)
    
    handler1.assert_called_once_with(event)
    handler2.assert_called_once_with(event)


def test_unsubscribe(event_bus):
    """测试取消订阅"""
    handler = Mock()
    event_bus.subscribe(DecisionRunCreated, handler)
    event_bus.unsubscribe(DecisionRunCreated, handler)
    
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event)
    
    handler.assert_not_called()


def test_get_subscribers(event_bus):
    """测试获取订阅者"""
    handler1 = Mock()
    handler2 = Mock()
    
    event_bus.subscribe(DecisionRunCreated, handler1)
    event_bus.subscribe(DecisionRunCreated, handler2)
    
    subscribers = event_bus.get_subscribers(DecisionRunCreated)
    
    assert len(subscribers) == 2
    assert handler1 in subscribers
    assert handler2 in subscribers


def test_get_published_events_by_type(event_bus):
    """测试按类型获取已发布的事件"""
    event1 = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event2 = DecisionRunCreated(
        decision_run_id="dr-456",
        symbol="000001.SZ",
        action="SELL",
        confidence=0.7,
        target_position_ratio=0.1,
        reason="Weak signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event1)
    event_bus.publish(event2)
    
    events = event_bus.get_published_events_by_type(DecisionRunCreated)
    assert len(events) == 2
    assert events[0] == event1
    assert events[1] == event2


def test_clear_published_events(event_bus):
    """测试清除已发布的事件"""
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_bus.publish(event)
    assert len(event_bus.get_published_events()) == 1
    
    event_bus.clear_published_events()
    assert len(event_bus.get_published_events()) == 0


def test_clear_subscribers(event_bus):
    """测试清除订阅者"""
    handler = Mock()
    event_bus.subscribe(DecisionRunCreated, handler)
    
    event_bus.clear_subscribers()
    
    subscribers = event_bus.get_subscribers(DecisionRunCreated)
    assert len(subscribers) == 0


def test_handler_exception_does_not_break_other_handlers(event_bus):
    """测试处理器异常不影响其他处理器"""
    def failing_handler(event):
        raise ValueError("Handler failed")
    
    success_handler = Mock()
    
    event_bus.subscribe(DecisionRunCreated, failing_handler)
    event_bus.subscribe(DecisionRunCreated, success_handler)
    
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    # 应该不会抛出异常
    event_bus.publish(event)
    
    # 成功的处理器应该被调用
    success_handler.assert_called_once_with(event)
