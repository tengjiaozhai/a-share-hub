import json
import uuid

from sqlalchemy import or_, select

from src.storage.models import BrokerEventRow, ExecutionOrderRow, KillSwitchEventRow, KillSwitchRow


class SystemRuntimeStore:
    """全局系统操作（与具体用户无关）。"""

    def __init__(self, engine) -> None:
        self.engine = engine

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

    def list_kill_switch_events(self, limit: int | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = select(KillSwitchEventRow).order_by(KillSwitchEventRow.created_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "kill_switch_event_id": row.kill_switch_event_id,
                    "active": row.active,
                    "reason": row.reason,
                    "actor_user_id": row.actor_user_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def insert_kill_switch_event(
        self,
        actor_user_id: str,
        active: bool,
        reason: str | None = None,
    ) -> None:
        event_id = f"kse-{uuid.uuid4().hex[:12]}"
        event_reason = reason or ""
        with self.engine.begin() as conn:
            conn.execute(
                KillSwitchEventRow.__table__.insert().values(
                    kill_switch_event_id=event_id,
                    active=active,
                    reason=event_reason,
                    actor_user_id=actor_user_id,
                )
            )
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def resolve_execution_order_owner(self, order_id: str) -> tuple[str, str, str] | None:
        """只读诊断：根据内部/券商订单号查找 owner。

        写入路径应使用 record_broker_event 在同一事务内完成。
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(
                    ExecutionOrderRow.user_id,
                    ExecutionOrderRow.execution_order_id,
                    ExecutionOrderRow.run_context_id,
                ).where(
                    or_(
                        ExecutionOrderRow.execution_order_id == order_id,
                        ExecutionOrderRow.broker_order_id == order_id,
                    )
                )
            ).one_or_none()
        return tuple(row) if row else None

    def record_broker_event(
        self,
        event_id: str,
        order_id: str,
        event_type: str,
        payload: dict,
    ) -> str:
        """根据 order_id 反查 execution_orders.owner，写入 broker_events。

        owner 解析和事件写入必须共享同一事务，避免 owner 在写入前被修改。
        """
        clean_payload = {key: value for key, value in payload.items() if key != "user_id"}
        with self.engine.begin() as conn:
            owner = conn.execute(
                select(
                    ExecutionOrderRow.user_id,
                    ExecutionOrderRow.execution_order_id,
                    ExecutionOrderRow.run_context_id,
                ).where(
                    or_(
                        ExecutionOrderRow.execution_order_id == order_id,
                        ExecutionOrderRow.broker_order_id == order_id,
                    )
                )
            ).one_or_none()
            if owner is None:
                raise LookupError(f"execution order not found: {order_id}")
            user_id, execution_order_id, run_context_id = owner
            conn.execute(
                BrokerEventRow.__table__.insert().values(
                    event_id=event_id,
                    user_id=user_id,
                    order_id=execution_order_id,
                    run_context_id=run_context_id,
                    event_type=event_type,
                    payload_json=json.dumps(clean_payload, ensure_ascii=True, sort_keys=True),
                )
            )
        return user_id
