from collections.abc import Callable

from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.infrastructure.event_bus.event_bus import EventBus


class DecisionEventHandlers:
    """决策事件处理器"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """设置事件处理器"""
        self.event_bus.subscribe(DecisionRunCreated, self._handle_decision_run_created)
        self.event_bus.subscribe(DecisionRunFailed, self._handle_decision_run_failed)

    def _handle_decision_run_created(self, event: DecisionRunCreated) -> None:
        """处理决策运行创建事件"""
        print(f"Decision run created: {event.decision_run_id} for {event.symbol}")

        # 这里可以添加其他业务逻辑，比如：
        # 1. 发送通知
        # 2. 更新统计信息
        # 3. 触发其他工作流

        # 示例：记录日志
        self._log_event(event)

    def _handle_decision_run_failed(self, event: DecisionRunFailed) -> None:
        """处理决策运行失败事件"""
        print(f"Decision run failed: {event.decision_run_id} for {event.symbol}. Error: {event.error}")

        # 这里可以添加其他业务逻辑，比如：
        # 1. 发送警报
        # 2. 记录错误统计
        # 3. 触发重试机制

        # 示例：记录日志
        self._log_event(event)

    def _log_event(self, event) -> None:
        """记录事件日志"""
        event_dict = event.to_dict()
        print(f"Event logged: {event_dict}")

    def get_handlers(self) -> dict[str, Callable]:
        """获取所有处理器"""
        return {
            "DecisionRunCreated": self._handle_decision_run_created,
            "DecisionRunFailed": self._handle_decision_run_failed,
        }
