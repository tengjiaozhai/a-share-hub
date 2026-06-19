from abc import ABC, abstractmethod
from typing import Any


class DecisionRunRepository(ABC):
    """决策运行仓储接口（按 user_id 隔离）"""

    @abstractmethod
    def insert_decision_run(
        self,
        user_id: str,
        symbol: str,
        prompt_hash: str,
        model_name: str,
        raw_output: str,
        parsed_action: str,
        confidence: int,
        target_position_ratio: float,
        reason: str,
        input_snapshot: dict,
        run_context_id: str | None = None,
    ) -> str:
        """插入决策运行记录"""
        pass

    @abstractmethod
    def get_decision_run(self, user_id: str, decision_run_id: str) -> dict[str, Any] | None:
        """获取决策运行记录"""
        pass

    @abstractmethod
    def list_decision_runs(self, user_id: str) -> list[dict[str, Any]]:
        """列出指定用户的所有决策运行记录"""
        pass

    @abstractmethod
    def delete_decision_run(self, user_id: str, decision_run_id: str) -> bool:
        """删除决策运行记录"""
        pass
