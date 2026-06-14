from typing import Dict, Any, Optional
import uuid
from src.domain.interfaces.decision_run_repository import DecisionRunRepository


class InMemoryDecisionRunRepository(DecisionRunRepository):
    """内存实现的决策运行仓储，用于测试"""
    
    def __init__(self):
        self._decision_runs: Dict[str, Dict[str, Any]] = {}
    
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
        decision_run_id = f"dr-{uuid.uuid4().hex[:12]}"
        self._decision_runs[decision_run_id] = {
            "decision_run_id": decision_run_id,
            "symbol": symbol,
            "prompt_hash": prompt_hash,
            "model_name": model_name,
            "raw_output": raw_output,
            "parsed_action": parsed_action,
            "confidence": confidence,
            "target_position_ratio": target_position_ratio,
            "reason": reason,
            "input_snapshot": input_snapshot,
            "run_context_id": run_context_id or decision_run_id,
        }
        return decision_run_id
    
    def get_decision_run(self, decision_run_id: str) -> Optional[Dict[str, Any]]:
        """获取决策运行记录"""
        return self._decision_runs.get(decision_run_id)
    
    def list_decision_runs(self) -> list[Dict[str, Any]]:
        """列出所有决策运行记录"""
        return list(self._decision_runs.values())
