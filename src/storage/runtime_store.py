import json
import uuid
from datetime import datetime

from sqlalchemy import func, select

from src.storage.models import (
    BrokerEventRow,
    DecisionInputSnapshotRow,
    DecisionRunRow,
    ExecutionOrderRow,
    ExecutionPlanRow,
    KillSwitchEventRow,
    KillSwitchRow,
    TargetPositionRow,
)


class RuntimeStore:
    def __init__(self, engine) -> None:
        self.engine = engine

    def insert_execution_plan(self, symbol: str, action: str, target_value: int, reason: str) -> str:
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.insert().values(
                    plan_id=plan_id,
                    symbol=symbol,
                    action=action,
                    target_value=target_value,
                    reason=reason,
                    status="READY",
                )
            )
        return plan_id

    def list_ready_execution_plans(self) -> list[dict]:
        with self.engine.begin() as conn:
            result = conn.execute(
                select(ExecutionPlanRow).where(ExecutionPlanRow.status == "READY").order_by(ExecutionPlanRow.created_at)
            )
            rows = result.fetchall()
            return [
                {
                    "plan_id": row.plan_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "reason": row.reason,
                }
                for row in rows
            ]

    def mark_plan_acknowledged(self, plan_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.update().where(ExecutionPlanRow.plan_id == plan_id).values(status="ACKNOWLEDGED")
            )

    def insert_broker_event(self, event_id: str, order_id: str, event_type: str, payload: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                BrokerEventRow.__table__.insert().values(
                    event_id=event_id,
                    order_id=order_id,
                    event_type=event_type,
                    payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                )
            )

    def set_kill_switch(self, active: bool) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def get_kill_switch(self) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1))
            row = result.one_or_none()
            return bool(row.active) if row is not None else False

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
    ) -> str:
        decision_run_id = f"dr-{uuid.uuid4().hex[:12]}"
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                DecisionRunRow.__table__.insert().values(
                    decision_run_id=decision_run_id,
                    symbol=symbol,
                    prompt_hash=prompt_hash,
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

    def get_decision_run(self, decision_run_id: str) -> dict:
        with self.engine.begin() as conn:
            run_result = conn.execute(
                select(DecisionRunRow).where(DecisionRunRow.decision_run_id == decision_run_id)
            )
            run_row = run_result.fetchone()
            snapshot_result = conn.execute(
                select(DecisionInputSnapshotRow).where(DecisionInputSnapshotRow.decision_run_id == decision_run_id)
            )
            snapshot_row = snapshot_result.fetchone()
            return {
                "decision_run_id": run_row[0],
                "symbol": run_row[1],
                "parsed_action": run_row[5],
                "confidence": run_row[6],
                "target_position_ratio": run_row[7],
                "reason": run_row[8],
                "snapshot": json.loads(snapshot_row[2]),
            }

    def list_decision_runs(self) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(DecisionRunRow).order_by(DecisionRunRow.created_at.desc())
            ).fetchall()
            return [
                {
                    "decision_run_id": row.decision_run_id,
                    "symbol": row.symbol,
                    "parsed_action": row.parsed_action,
                    "confidence": row.confidence,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def insert_target_position(
        self,
        decision_run_id: str,
        symbol: str,
        action: str,
        target_value: int,
        target_position_ratio: float,
        expires_at: str,
    ) -> str:
        target_position_id = f"tp-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                TargetPositionRow.__table__.insert().values(
                    target_position_id=target_position_id,
                    decision_run_id=decision_run_id,
                    symbol=symbol,
                    action=action,
                    target_value=target_value,
                    target_position_ratio=target_position_ratio,
                    expires_at=datetime.fromisoformat(expires_at),
                    status="ACTIVE",
                )
            )
        return target_position_id

    def list_active_target_positions(self) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(TargetPositionRow)
                .where(TargetPositionRow.status == "ACTIVE")
                .order_by(TargetPositionRow.created_at.desc())
            ).fetchall()
            return [
                {
                    "target_position_id": row.target_position_id,
                    "decision_run_id": row.decision_run_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "target_position_ratio": row.target_position_ratio,
                    "expires_at": row.expires_at.isoformat(),
                }
                for row in rows
            ]

    def insert_execution_order(
        self,
        target_position_id: str,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
    ) -> str:
        execution_order_id = f"eo-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionOrderRow.__table__.insert().values(
                    execution_order_id=execution_order_id,
                    target_position_id=target_position_id,
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    limit_price=limit_price,
                    status="READY",
                )
            )
        return execution_order_id

    def insert_broker_order_event(
        self,
        execution_order_id: str,
        event_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                BrokerEventRow.__table__.insert().values(
                    event_id=event_id,
                    order_id=execution_order_id,
                    event_type=event_type,
                    payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                )
            )

    def get_reconciliation_status(self) -> dict:
        with self.engine.begin() as conn:
            open_orders = conn.execute(
                select(func.count()).select_from(ExecutionOrderRow).where(ExecutionOrderRow.status != "FILLED")
            ).scalar_one()
            broker_event_count = conn.execute(
                select(func.count()).select_from(BrokerEventRow)
            ).scalar_one()
        return {
            "open_orders": open_orders,
            "broker_event_count": broker_event_count,
            "healthy": open_orders == 0 or broker_event_count > 0,
        }

    def insert_kill_switch_event(self, active: bool, reason: str) -> None:
        event_id = f"kse-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                KillSwitchEventRow.__table__.insert().values(
                    kill_switch_event_id=event_id,
                    active=active,
                    reason=reason,
                )
            )
            # 同时更新 kill_switch_state
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))