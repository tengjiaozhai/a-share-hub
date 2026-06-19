from typing import Dict, Any, Optional
import uuid
from src.domain.interfaces.decision_run_repository import DecisionRunRepository


class InMemoryDecisionRunRepository(DecisionRunRepository):
    """内存实现的决策运行仓储，用于测试（按 user_id 隔离）"""

    def __init__(self):
        # key: (user_id, decision_run_id)
        self._decision_runs: Dict[tuple, Dict[str, Any]] = {}

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
        decision_run_id = f"dr-{uuid.uuid4().hex[:12]}"
        self._decision_runs[(user_id, decision_run_id)] = {
            "decision_run_id": decision_run_id,
            "user_id": user_id,
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

    def get_decision_run(self, user_id: str, decision_run_id: str) -> Optional[Dict[str, Any]]:
        return self._decision_runs.get((user_id, decision_run_id))

    def list_decision_runs(self, user_id: str) -> list[Dict[str, Any]]:
        return [
            row
            for (row_user, _key), row in self._decision_runs.items()
            if row_user == user_id
        ]

    def delete_decision_run(self, user_id: str, decision_run_id: str) -> bool:
        key = (user_id, decision_run_id)
        if key in self._decision_runs:
            del self._decision_runs[key]
            return True
        return False
