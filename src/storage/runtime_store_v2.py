import os
import sys
from typing import Any

from sqlalchemy.engine import Engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import SQLAlchemyDecisionRunRepository


class RuntimeStoreV2:
    """重构后的 RuntimeStore，使用 Repository 模式（按 user_id 隔离）"""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._decision_run_repository: DecisionRunRepository | None = None

    @property
    def decision_run_repository(self) -> DecisionRunRepository:
        if self._decision_run_repository is None:
            self._decision_run_repository = SQLAlchemyDecisionRunRepository(self.engine)
        return self._decision_run_repository

    def insert_decision_run(
        self,
        user_id: str,
        symbol: str,
        prompt_hash: str,
        model_name: str,
        raw_output: str,
        parsed_action: str,
        confidence: float,
        target_position_ratio: float,
        reason: str,
        input_snapshot: dict[str, Any],
    ) -> str:
        return self.decision_run_repository.insert_decision_run(
            user_id=user_id,
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

    def get_decision_run(self, user_id: str, decision_run_id: str) -> dict[str, Any] | None:
        return self.decision_run_repository.get_decision_run(user_id=user_id, decision_run_id=decision_run_id)

    def list_decision_runs(self, user_id: str) -> list[dict[str, Any]]:
        return self.decision_run_repository.list_decision_runs(user_id=user_id)

    def delete_decision_run(self, user_id: str, decision_run_id: str) -> bool:
        return self.decision_run_repository.delete_decision_run(user_id=user_id, decision_run_id=decision_run_id)
