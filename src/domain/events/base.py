import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DomainEvent(ABC):
    """领域事件基类"""

    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_type: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'event_type', self.__class__.__name__)

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        pass

    def __str__(self) -> str:
        return f"{self.event_type}(id={self.event_id}, occurred_at={self.occurred_at})"


@dataclass(frozen=True)
class EventMetadata:
    """事件元数据"""

    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "source": self.source,
        }
