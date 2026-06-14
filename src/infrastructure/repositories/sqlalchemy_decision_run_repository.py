import json
import uuid
from typing import Any

from sqlalchemy import select

from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.storage.models import DecisionInputSnapshotRow, DecisionRunRow


class SQLAlchemyDecisionRunRepository(DecisionRunRepository):
    """SQLAlchemy决策运行仓储实现"""

    def __init__(self, engine):
        self.engine = engine

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
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        effective_run_context_id = run_context_id or decision_run_id
        with self.engine.begin() as conn:
            conn.execute(
                DecisionRunRow.__table__.insert().values(
                    decision_run_id=decision_run_id,
                    symbol=symbol,
                    prompt_hash=prompt_hash,
                    run_context_id=effective_run_context_id,
                    model_name=model_name,
                    raw_output=raw_output,
                    parsed_action=parsed_action,
                    confidence=confidence,
                    target_position_ratio=target_position_ratio,
                    reason=reason,
                )
            )
            conn.execute(
                DecisionInputSnapshotRow.__table__.insert().values(
                    snapshot_id=snapshot_id,
                    decision_run_id=decision_run_id,
                    payload_json=json.dumps(input_snapshot, ensure_ascii=True, sort_keys=True),
                )
            )
        return decision_run_id

    def get_decision_run(self, decision_run_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            run_result = conn.execute(
                select(DecisionRunRow).where(DecisionRunRow.decision_run_id == decision_run_id)
            )
            run_row = run_result.fetchone()
            snapshot_result = conn.execute(
                select(DecisionInputSnapshotRow).where(DecisionInputSnapshotRow.decision_run_id == decision_run_id)
            )
            snapshot_row = snapshot_result.fetchone()

        if run_row is None:
            return None

        return {
            "decision_run_id": run_row.decision_run_id,
            "symbol": run_row.symbol,
            "prompt_hash": run_row.prompt_hash,
            "run_context_id": run_row.run_context_id,
            "model_name": run_row.model_name,
            "raw_output": run_row.raw_output,
            "parsed_action": run_row.parsed_action,
            "confidence": run_row.confidence,
            "target_position_ratio": run_row.target_position_ratio,
            "reason": run_row.reason,
            "input_snapshot": json.loads(snapshot_row.payload_json) if snapshot_row else {},
        }

    def list_decision_runs(self) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            result = conn.execute(select(DecisionRunRow))
            rows = result.fetchall()

        return [
            {
                "decision_run_id": row.decision_run_id,
                "symbol": row.symbol,
                "prompt_hash": row.prompt_hash,
                "run_context_id": row.run_context_id,
                "model_name": row.model_name,
                "raw_output": row.raw_output,
                "parsed_action": row.parsed_action,
                "confidence": row.confidence,
                "target_position_ratio": row.target_position_ratio,
                "reason": row.reason,
            }
            for row in rows
        ]
