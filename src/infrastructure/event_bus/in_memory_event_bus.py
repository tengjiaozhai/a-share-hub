from collections import defaultdict
from collections.abc import Callable

from src.domain.events.base import DomainEvent
from src.infrastructure.event_bus.event_bus import EventBus


class InMemoryEventBus(EventBus):
    """内存事件总线实现，用于测试"""

    def __init__(self):
        self._subscribers: dict[type[DomainEvent], set[Callable[[DomainEvent], None]]] = defaultdict(set)
        self._published_events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        """发布事件"""
        self._published_events.append(event)

        # 获取事件类型
        event_type = type(event)

        # 调用所有订阅者
        for handler in self._subscribers.get(event_type, set()):
            try:
                handler(event)
            except Exception as e:
                # 记录错误但不中断其他处理器
                print(f"Error in event handler: {e}")

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """订阅事件"""
        self._subscribers[event_type].add(handler)

    def unsubscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)

    def get_subscribers(self, event_type: type[DomainEvent]) -> list[Callable[[DomainEvent], None]]:
        """获取事件订阅者"""
        return list(self._subscribers.get(event_type, set()))

    def get_published_events(self) -> list[DomainEvent]:
        """获取所有已发布的事件"""
        return self._published_events.copy()

    def get_published_events_by_type(self, event_type: type[DomainEvent]) -> list[DomainEvent]:
        """按类型获取已发布的事件"""
        return [event for event in self._published_events if isinstance(event, event_type)]

    def clear_published_events(self) -> None:
        """清除所有已发布的事件"""
        self._published_events.clear()

    def clear_subscribers(self) -> None:
        """清除所有订阅者"""
        self._subscribers.clear()
