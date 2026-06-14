from typing import Dict, Any, Optional, List
from sqlalchemy.engine import Engine

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import SQLAlchemyDecisionRunRepository


class RuntimeStoreV2:
    """重构后的RuntimeStore，使用Repository模式"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self._decision_run_repository: Optional[DecisionRunRepository] = None
    
    @property
    def decision_run_repository(self) -> DecisionRunRepository:
        if self._decision_run_repository is None:
            self._decision_run_repository = SQLAlchemyDecisionRunRepository(self.engine)
        return self._decision_run_repository
    
    def insert_decision_run(
        self,
        symbol: str,
        prompt_hash: str,
        model_name: str,
        raw_output: str,
        parsed_action: str,
        confidence: float,
        target_position_ratio: float,
        reason: str,
        input_snapshot: Dict[str, Any],
    ) -> str:
        """插入决策运行记录"""
        return self.decision_run_repository.insert_decision_run(
            symbol=symbol,
            prompt_hash=prompt_hash,
            model_name=model_name,
            raw_output=raw_output,
            parsed_action=parsed_action,
            confidence=confidence,
            target_position_ratio=target_position_ratio,
            reason=reason,
            input_snapshot=input_snapshot,
        )
    
    def get_decision_run(self, decision_run_id: str) -> Optional[Dict[str, Any]]:
        """获取决策运行记录"""
        return self.decision_run_repository.get_decision_run(decision_run_id)
    
    def list_decision_runs(self) -> List[Dict[str, Any]]:
        """列出决策运行记录"""
        return self.decision_run_repository.list_decision_runs()
    
    def delete_decision_run(self, decision_run_id: str) -> bool:
        """删除决策运行记录"""
        return self.decision_run_repository.delete_decision_run(decision_run_id)