from typing import Dict, Any, Optional
import uuid

from src.domain.interfaces.decision_run_repository import DecisionRunRepository


class InMemoryDecisionRunRepository(DecisionRunRepository):
    """内存决策运行仓储实现（用于测试）"""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
    
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
        decision_run_id = f"dr-{uuid.uuid4().hex[:12]}"
        self._store[decision_run_id] = {
            "decision_run_id": decision_run_id,
            "symbol": symbol,
            "prompt_hash": prompt_hash,
            "run_context_id": run_context_id or decision_run_id,
            "model_name": model_name,
            "raw_output": raw_output,
            "parsed_action": parsed_action,
            "confidence": confidence,
            "target_position_ratio": target_position_ratio,
            "reason": reason,
            "input_snapshot": input_snapshot,
        }
        return decision_run_id
    
    def get_decision_run(self, decision_run_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(decision_run_id)
    
    def list_decision_runs(self) -> list[Dict[str, Any]]:
        return list(self._store.values())
