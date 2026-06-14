from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class DecisionRunRepository(ABC):
    """决策运行仓储接口"""
    
    @abstractmethod
    def insert_decision_run(
        self,
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
    def get_decision_run(self, decision_run_id: str) -> Optional[Dict[str, Any]]:
        """获取决策运行记录"""
        pass
    
    @abstractmethod
    def list_decision_runs(self) -> list[Dict[str, Any]]:
        """列出所有决策运行记录"""
        pass
    
    @abstractmethod
    def delete_decision_run(self, decision_run_id: str) -> bool:
        """删除决策运行记录"""
        pass
