from dataclasses import dataclass
from typing import Any

from .base import DomainEvent, EventMetadata


@dataclass(frozen=True)
class DecisionRunCreated(DomainEvent):
    """决策运行创建事件"""

    decision_run_id: str = ""
    symbol: str = ""
    action: str = ""
    confidence: float = 0.0
    target_position_ratio: float = 0.0
    reason: str = ""
    model_name: str = ""
    metadata: EventMetadata | None = None

    def __post_init__(self):
        super().__post_init__()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "decision_run_id": self.decision_run_id,
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "target_position_ratio": self.target_position_ratio,
            "reason": self.reason,
            "model_name": self.model_name,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result


@dataclass(frozen=True)
class DecisionRunFailed(DomainEvent):
    """决策运行失败事件"""

    decision_run_id: str = ""
    symbol: str = ""
    error: str = ""
    model_name: str = ""
    metadata: EventMetadata | None = None

    def __post_init__(self):
        super().__post_init__()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "decision_run_id": self.decision_run_id,
            "symbol": self.symbol,
            "error": self.error,
            "model_name": self.model_name,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result


@dataclass(frozen=True)
class DecisionActionChanged(DomainEvent):
    """决策动作变更事件"""

    decision_run_id: str = ""
    symbol: str = ""
    old_action: str = ""
    new_action: str = ""
    reason: str = ""
    metadata: EventMetadata | None = None

    def __post_init__(self):
        super().__post_init__()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "decision_run_id": self.decision_run_id,
            "symbol": self.symbol,
            "old_action": self.old_action,
            "new_action": self.new_action,
            "reason": self.reason,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result
