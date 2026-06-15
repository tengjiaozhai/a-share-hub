from abc import ABC, abstractmethod
from collections.abc import Callable

from src.domain.events.base import DomainEvent


class EventBus(ABC):
    """事件总线抽象接口"""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """发布事件"""
        pass

    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """订阅事件"""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        """取消订阅"""
        pass

    @abstractmethod
    def get_subscribers(self, event_type: type[DomainEvent]) -> list[Callable[[DomainEvent], None]]:
        """获取事件订阅者"""
        pass
