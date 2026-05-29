import json
import uuid
from datetime import datetime, timedelta, timezone

_CST = timezone(timedelta(hours=8))


def _to_cst(dt: datetime) -> datetime:
    """将无时区的 UTC datetime 转为 CST（UTC+8）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_CST)


def _cst_iso(dt: datetime) -> str:
    return _to_cst(dt).isoformat()

from sqlalchemy import func, select

from src.storage.models import (
    AccountSnapshotRow,
    BrokerEventRow,
    DecisionInputSnapshotRow,
    DecisionRunRow,
    ExecutionOrderRow,
    ExecutionPlanRow,
    KillSwitchEventRow,
    KillSwitchRow,
    TargetPositionRow,
    UserPreferenceRow,
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
                    "created_at": _cst_iso(row.created_at),
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

    def list_decision_runs(self, limit: int | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = select(DecisionRunRow).order_by(DecisionRunRow.created_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "decision_run_id": row.decision_run_id,
                    "prompt_hash": row.prompt_hash,
                    "symbol": row.symbol,
                    "parsed_action": row.parsed_action,
                    "confidence": row.confidence,
                    "target_position_ratio": row.target_position_ratio,
                    "reason": row.reason,
                    "input_snapshot": self._get_decision_input_snapshot(conn, row.decision_run_id),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def _get_decision_input_snapshot(self, conn, decision_run_id: str) -> dict:
        snapshot_row = conn.execute(
            select(DecisionInputSnapshotRow.payload_json).where(
                DecisionInputSnapshotRow.decision_run_id == decision_run_id
            )
        ).one_or_none()
        if snapshot_row is None:
            return {}
        return json.loads(snapshot_row[0])

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

    def list_active_target_positions(self, limit: int | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            now = datetime.utcnow()
            stmt = (
                select(TargetPositionRow)
                .where(TargetPositionRow.status == "ACTIVE")
                .where(TargetPositionRow.expires_at > now)
                .order_by(TargetPositionRow.created_at.desc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "target_position_id": row.target_position_id,
                    "decision_run_id": row.decision_run_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "target_position_ratio": row.target_position_ratio,
                    "status": row.status,
                    "expires_at": _cst_iso(row.expires_at),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def deactivate_expired_targets(self) -> int:
        """将已过期的 ACTIVE 目标标记为 EXPIRED，返回更新数量。"""
        now = datetime.utcnow()
        with self.engine.begin() as conn:
            result = conn.execute(
                TargetPositionRow.__table__.update()
                .where(TargetPositionRow.status == "ACTIVE")
                .where(TargetPositionRow.expires_at <= now)
                .values(status="EXPIRED")
            )
            return result.rowcount

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

    def update_execution_order_status(
        self,
        execution_order_id: str,
        status: str,
        broker_order_id: str | None = None,
    ) -> None:
        values: dict[str, str] = {"status": status}
        if broker_order_id is not None:
            values["broker_order_id"] = broker_order_id
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionOrderRow.__table__.update()
                .where(ExecutionOrderRow.execution_order_id == execution_order_id)
                .values(**values)
            )

    def list_execution_orders(self, limit: int | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = select(ExecutionOrderRow).order_by(ExecutionOrderRow.created_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "execution_order_id": row.execution_order_id,
                    "target_position_id": row.target_position_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "quantity": row.quantity,
                    "limit_price": row.limit_price,
                    "status": row.status,
                     "broker_order_id": row.broker_order_id,
                     "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def list_broker_events(self, limit: int | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = select(BrokerEventRow).order_by(BrokerEventRow.created_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "event_id": row.event_id,
                    "order_id": row.order_id,
                    "event_type": row.event_type,
                     "payload": json.loads(row.payload_json),
                     "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

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
                     "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

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

    def sum_daily_pnl(self, trade_date: str | None = None) -> float:
        if trade_date:
            # 调用方传入的日期字符串按 CST 日边界解释
            cst_today = datetime.fromisoformat(trade_date).replace(tzinfo=_CST)
        else:
            cst_today = datetime.now(_CST)
        # CST 当天 00:00:00 ~ 次日 00:00:00，转回 UTC 与数据库比较
        day_start_cst = cst_today.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end_cst = day_start_cst + timedelta(days=1)
        day_start = day_start_cst.astimezone(timezone.utc).replace(tzinfo=None)
        day_end = day_end_cst.astimezone(timezone.utc).replace(tzinfo=None)

        with self.engine.begin() as conn:
            rows = conn.execute(
                select(BrokerEventRow.payload_json).where(
                    BrokerEventRow.event_type == "FILLED",
                    BrokerEventRow.created_at >= day_start,
                    BrokerEventRow.created_at < day_end,
                )
            ).fetchall()

        total = 0.0
        for row in rows:
            payload = json.loads(row.payload_json)
            try:
                total += float(payload.get("pnl_delta", 0.0))
            except (TypeError, ValueError):
                continue
        return round(total, 2)

    def insert_kill_switch_event(self, active: bool, reason: str | None = None) -> None:
        event_id = f"kse-{uuid.uuid4().hex[:12]}"
        event_reason = reason or ""
        with self.engine.begin() as conn:
            conn.execute(
                KillSwitchEventRow.__table__.insert().values(
                    kill_switch_event_id=event_id,
                    active=active,
                    reason=event_reason,
                )
            )
            # 同时更新 kill_switch_state
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def insert_account_snapshot(self, cash: float, nav: float, positions: dict) -> str:
        snapshot_id = f"acct-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                AccountSnapshotRow.__table__.insert().values(
                    snapshot_id=snapshot_id,
                    cash=cash,
                    nav=nav,
                    positions_json=json.dumps(positions, ensure_ascii=True),
                )
            )
        return snapshot_id

    def get_latest_account_snapshot(self) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(AccountSnapshotRow).order_by(AccountSnapshotRow.created_at.desc()).limit(1)
            ).fetchone()
        if row is None:
            return None
        return {
            "snapshot_id": row.snapshot_id,
            "cash": row.cash,
            "nav": row.nav,
            "positions": json.loads(row.positions_json),
            "created_at": row.created_at.isoformat(),
        }

    def get_preference(self, key: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(UserPreferenceRow).where(UserPreferenceRow.key == key)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row.value)

    def set_preference(self, key: str, value: dict) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(UserPreferenceRow).where(UserPreferenceRow.key == key)
            ).fetchone()
            if existing is not None:
                conn.execute(
                    UserPreferenceRow.__table__.update()
                    .where(UserPreferenceRow.key == key)
                    .values(value=json.dumps(value, ensure_ascii=True))
                )
            else:
                conn.execute(
                    UserPreferenceRow.__table__.insert().values(
                        key=key,
                        value=json.dumps(value, ensure_ascii=True),
                    )
                )
