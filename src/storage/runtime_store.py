import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

_CST = timezone(timedelta(hours=8))


def _to_cst(dt: datetime) -> datetime:
    """将无时区的 UTC datetime 转为 CST（UTC+8）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_CST)


def _cst_iso(dt: datetime) -> str:
    return _to_cst(dt).isoformat()


def _parse_summary_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(UTC).replace(tzinfo=None)

from sqlalchemy import func, select

from src.storage.models import (
    AccountSnapshotRow,
    AlphaApiOrderAttemptRow,
    AlphaManualFillRow,
    AlphaPortfolioSnapshotRow,
    AlphaPositionRow,
    AlphaReconciliationRunRow,
    AlphaTicketRow,
    AlphaWatchlistItemRow,
    BrokerEventRow,
    DashboardRunEventRow,
    DashboardRunSummaryRow,
    DecisionInputSnapshotRow,
    DecisionRunRow,
    ExecutionOrderRow,
    ExecutionPlanRow,
    KillSwitchEventRow,
    KillSwitchRow,
    RiskGateEventRow,
    TargetPositionRow,
    UserPreferenceRow,
)


class RuntimeStore:
    def __init__(self, engine) -> None:
        self.engine = engine

    def insert_execution_plan(
        self,
        user_id: str,
        symbol: str,
        action: str,
        target_value: int,
        reason: str,
    ) -> str:
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.insert().values(
                    plan_id=plan_id,
                    user_id=user_id,
                    symbol=symbol,
                    action=action,
                    target_value=target_value,
                    reason=reason,
                    status="READY",
                )
            )
        return plan_id

    def list_ready_execution_plans(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            result = conn.execute(
                select(ExecutionPlanRow)
                .where(ExecutionPlanRow.user_id == user_id)
                .where(ExecutionPlanRow.status == "READY")
                .order_by(ExecutionPlanRow.created_at)
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

    def mark_plan_acknowledged(self, user_id: str, plan_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.update()
                .where(ExecutionPlanRow.plan_id == plan_id)
                .where(ExecutionPlanRow.user_id == user_id)
                .values(status="ACKNOWLEDGED")
            )

    def insert_broker_event(self, event_id: str, order_id: str, event_type: str, payload: dict) -> None:
        # 全局表（HMAC 验签），不带 user_id
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
        # 全局系统状态，不带 user_id
        with self.engine.begin() as conn:
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def get_kill_switch(self) -> bool:
        # 全局系统状态，不带 user_id
        with self.engine.begin() as conn:
            result = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1))
            row = result.one_or_none()
            return bool(row.active) if row is not None else False

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
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        effective_run_context_id = run_context_id or decision_run_id
        with self.engine.begin() as conn:
            conn.execute(
                DecisionRunRow.__table__.insert().values(
                    decision_run_id=decision_run_id,
                    user_id=user_id,
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
                    user_id=user_id,
                    decision_run_id=decision_run_id,
                    payload_json=json.dumps(input_snapshot, ensure_ascii=True, sort_keys=True),
                )
            )
        return decision_run_id

    def get_decision_run(self, user_id: str, decision_run_id: str) -> dict | None:
        with self.engine.begin() as conn:
            run_result = conn.execute(
                select(DecisionRunRow)
                .where(DecisionRunRow.decision_run_id == decision_run_id)
                .where(DecisionRunRow.user_id == user_id)
            )
            run_row = run_result.fetchone()
            if run_row is None:
                return None
            snapshot_result = conn.execute(
                select(DecisionInputSnapshotRow.payload_json)
                .where(DecisionInputSnapshotRow.decision_run_id == decision_run_id)
                .where(DecisionInputSnapshotRow.user_id == user_id)
            )
            snapshot_row = snapshot_result.one_or_none()
            return {
                "decision_run_id": run_row.decision_run_id,
                "symbol": run_row.symbol,
                "parsed_action": run_row.parsed_action,
                "confidence": run_row.confidence,
                "target_position_ratio": run_row.target_position_ratio,
                "reason": run_row.reason,
                "snapshot": json.loads(snapshot_row[0]) if snapshot_row else {},
            }

    def list_decision_runs(
        self,
        user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = (
                select(DecisionRunRow)
                .where(DecisionRunRow.user_id == user_id)
                .order_by(DecisionRunRow.created_at.desc())
            )
            if limit is not None:
                stmt = stmt.offset(offset).limit(limit)
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
                    "input_snapshot": self._get_decision_input_snapshot(conn, user_id, row.decision_run_id),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def count_decision_runs(self, user_id: str) -> int:
        with self.engine.begin() as conn:
            stmt = (
                select(func.count())
                .select_from(DecisionRunRow)
                .where(DecisionRunRow.user_id == user_id)
            )
            return conn.execute(stmt).scalar()

    def _get_decision_input_snapshot(self, conn, user_id: str, decision_run_id: str) -> dict:
        snapshot_row = conn.execute(
            select(DecisionInputSnapshotRow.payload_json)
            .where(DecisionInputSnapshotRow.decision_run_id == decision_run_id)
            .where(DecisionInputSnapshotRow.user_id == user_id)
        ).one_or_none()
        if snapshot_row is None:
            return {}
        return json.loads(snapshot_row[0])

    def insert_target_position(
        self,
        user_id: str,
        decision_run_id: str,
        symbol: str,
        action: str,
        target_value: int,
        target_position_ratio: float,
        expires_at: str,
        run_context_id: str | None = None,
        status: str = "ACTIVE",
        status_reason: str = "ready",
        price: float = 0.0,
        lot_size: int = 0,
        requested_quantity: float = 0.0,
        notional: int = 0,
        diagnostics: dict | None = None,
    ) -> str:
        target_position_id = f"tp-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            effective_run_context_id = run_context_id or conn.execute(
                select(DecisionRunRow.run_context_id)
                .where(DecisionRunRow.decision_run_id == decision_run_id)
                .where(DecisionRunRow.user_id == user_id)
            ).scalar_one()
            conn.execute(
                TargetPositionRow.__table__.insert().values(
                    target_position_id=target_position_id,
                    user_id=user_id,
                    decision_run_id=decision_run_id,
                    run_context_id=effective_run_context_id,
                    symbol=symbol,
                    action=action,
                    target_value=target_value,
                    target_position_ratio=target_position_ratio,
                    status=status,
                    status_reason=status_reason,
                    price=price,
                    lot_size=lot_size,
                    requested_quantity=requested_quantity,
                    notional=notional,
                    diagnostics_json=json.dumps(diagnostics or {}, ensure_ascii=True, sort_keys=True),
                    expires_at=datetime.fromisoformat(expires_at),
                )
            )
        return target_position_id

    def list_active_target_positions(
        self,
        user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            now = datetime.utcnow()
            stmt = (
                select(TargetPositionRow)
                .where(TargetPositionRow.user_id == user_id)
                .where(TargetPositionRow.status == "ACTIVE")
                .where(TargetPositionRow.expires_at > now)
                .order_by(TargetPositionRow.created_at.desc())
            )
            if limit is not None:
                stmt = stmt.offset(offset).limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "target_position_id": row.target_position_id,
                    "decision_run_id": row.decision_run_id,
                    "run_context_id": row.run_context_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "target_position_ratio": row.target_position_ratio,
                    "status": row.status,
                    "status_reason": row.status_reason,
                    "price": row.price,
                    "lot_size": row.lot_size,
                    "requested_quantity": row.requested_quantity,
                    "notional": row.notional,
                    "diagnostics": json.loads(row.diagnostics_json or "{}"),
                    "expires_at": _cst_iso(row.expires_at),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def list_target_positions(
        self,
        user_id: str,
        limit: int | None = None,
        offset: int = 0,
        run_context_id: str | None = None,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = (
                select(TargetPositionRow)
                .where(TargetPositionRow.user_id == user_id)
                .order_by(TargetPositionRow.created_at.desc())
            )
            if run_context_id is not None:
                stmt = stmt.where(TargetPositionRow.run_context_id == run_context_id)
            if limit is not None:
                stmt = stmt.offset(offset).limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "target_position_id": row.target_position_id,
                    "decision_run_id": row.decision_run_id,
                    "run_context_id": row.run_context_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "target_position_ratio": row.target_position_ratio,
                    "status": row.status,
                    "status_reason": row.status_reason,
                    "price": row.price,
                    "lot_size": row.lot_size,
                    "requested_quantity": row.requested_quantity,
                    "notional": row.notional,
                    "diagnostics": json.loads(row.diagnostics_json or "{}"),
                    "expires_at": _cst_iso(row.expires_at),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def count_active_target_positions(self, user_id: str) -> int:
        with self.engine.begin() as conn:
            now = datetime.utcnow()
            stmt = (
                select(func.count())
                .select_from(TargetPositionRow)
                .where(TargetPositionRow.user_id == user_id)
                .where(TargetPositionRow.status == "ACTIVE")
                .where(TargetPositionRow.expires_at > now)
            )
            return conn.execute(stmt).scalar()

    def deactivate_expired_targets(self, user_id: str) -> int:
        """将属于指定用户且已过期的 ACTIVE 目标标记为 EXPIRED，返回更新数量。"""
        now = datetime.utcnow()
        with self.engine.begin() as conn:
            result = conn.execute(
                TargetPositionRow.__table__.update()
                .where(TargetPositionRow.user_id == user_id)
                .where(TargetPositionRow.status == "ACTIVE")
                .where(TargetPositionRow.expires_at <= now)
                .values(status="EXPIRED")
            )
            return result.rowcount

    def insert_execution_order(
        self,
        user_id: str,
        target_position_id: str,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
        run_context_id: str | None = None,
        status: str = "READY",
        status_code: str = "READY",
        status_reason: str = "ready",
        submitted_at: str | None = None,
        slippage_bps: float = 0.0,
    ) -> str:
        execution_order_id = f"eo-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            effective_run_context_id = run_context_id or conn.execute(
                select(TargetPositionRow.run_context_id)
                .where(TargetPositionRow.target_position_id == target_position_id)
                .where(TargetPositionRow.user_id == user_id)
            ).scalar_one()
            conn.execute(
                ExecutionOrderRow.__table__.insert().values(
                    execution_order_id=execution_order_id,
                    user_id=user_id,
                    target_position_id=target_position_id,
                    run_context_id=effective_run_context_id,
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    filled_quantity=0,
                    limit_price=limit_price,
                    status=status,
                    status_code=status_code,
                    status_reason=status_reason,
                    slippage_bps=slippage_bps,
                    submitted_at=datetime.fromisoformat(submitted_at) if submitted_at else None,
                )
            )
        return execution_order_id

    def insert_broker_order_event(
        self,
        execution_order_id: str,
        event_id: str,
        event_type: str,
        payload: dict,
        run_context_id: str | None = None,
    ) -> None:
        # 全局表（HMAC 验签），不带 user_id
        with self.engine.begin() as conn:
            effective_run_context_id = run_context_id or conn.execute(
                select(ExecutionOrderRow.run_context_id).where(ExecutionOrderRow.execution_order_id == execution_order_id)
            ).scalar_one()
            conn.execute(
                BrokerEventRow.__table__.insert().values(
                    event_id=event_id,
                    order_id=execution_order_id,
                    run_context_id=effective_run_context_id,
                    event_type=event_type,
                    payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                )
            )

    def update_execution_order_status(
        self,
        user_id: str,
        execution_order_id: str,
        status: str,
        *,
        broker_order_id: str | None = None,
        status_code: str | None = None,
        status_reason: str | None = None,
        filled_quantity: int | None = None,
        fill_price: float | None = None,
        fee: float | None = None,
        pnl_delta: float | None = None,
        filled_at: str | None = None,
        last_event_at: str | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status}
        if broker_order_id is not None:
            values["broker_order_id"] = broker_order_id
        if status_code is not None:
            values["status_code"] = status_code
        if status_reason is not None:
            values["status_reason"] = status_reason
        if filled_quantity is not None:
            values["filled_quantity"] = filled_quantity
        if fill_price is not None:
            values["fill_price"] = fill_price
        if fee is not None:
            values["fee"] = fee
        if pnl_delta is not None:
            values["pnl_delta"] = pnl_delta
        if filled_at is not None:
            values["filled_at"] = datetime.fromisoformat(filled_at)
        if last_event_at is not None:
            values["last_event_at"] = datetime.fromisoformat(last_event_at)
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionOrderRow.__table__.update()
                .where(ExecutionOrderRow.execution_order_id == execution_order_id)
                .where(ExecutionOrderRow.user_id == user_id)
                .values(**values)
            )

    def list_execution_orders(
        self,
        user_id: str,
        limit: int | None = None,
        offset: int = 0,
        run_context_id: str | None = None,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = (
                select(ExecutionOrderRow)
                .where(ExecutionOrderRow.user_id == user_id)
                .order_by(ExecutionOrderRow.created_at.desc())
            )
            if run_context_id is not None:
                stmt = stmt.where(ExecutionOrderRow.run_context_id == run_context_id)
            if limit is not None:
                stmt = stmt.offset(offset).limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "execution_order_id": row.execution_order_id,
                    "target_position_id": row.target_position_id,
                    "run_context_id": row.run_context_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "quantity": row.quantity,
                    "filled_quantity": row.filled_quantity,
                    "limit_price": row.limit_price,
                    "fill_price": row.fill_price,
                    "fee": row.fee,
                    "pnl_delta": row.pnl_delta,
                    "status": row.status,
                    "status_code": row.status_code,
                    "status_reason": row.status_reason,
                    "slippage_bps": row.slippage_bps,
                    "broker_order_id": row.broker_order_id,
                    "submitted_at": _cst_iso(row.submitted_at) if row.submitted_at else None,
                    "filled_at": _cst_iso(row.filled_at) if row.filled_at else None,
                    "last_event_at": _cst_iso(row.last_event_at) if row.last_event_at else None,
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def count_execution_orders(self, user_id: str) -> int:
        with self.engine.begin() as conn:
            stmt = (
                select(func.count())
                .select_from(ExecutionOrderRow)
                .where(ExecutionOrderRow.user_id == user_id)
            )
            return conn.execute(stmt).scalar()

    def list_broker_events(self, limit: int | None = None) -> list[dict]:
        # 全局表（HMAC 验签），不带 user_id
        with self.engine.begin() as conn:
            stmt = select(BrokerEventRow).order_by(BrokerEventRow.created_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "event_id": row.event_id,
                    "order_id": row.order_id,
                    "run_context_id": row.run_context_id,
                    "event_type": row.event_type,
                     "payload": json.loads(row.payload_json),
                     "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def insert_risk_gate_event(
        self,
        user_id: str,
        run_context_id: str,
        target_position_id: str | None,
        symbol: str,
        approved: bool,
        rule_name: str,
        reason: str,
        details: dict | None = None,
    ) -> str:
        risk_gate_event_id = f"rge-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                RiskGateEventRow.__table__.insert().values(
                    risk_gate_event_id=risk_gate_event_id,
                    user_id=user_id,
                    run_context_id=run_context_id,
                    target_position_id=target_position_id,
                    symbol=symbol,
                    approved=approved,
                    rule_name=rule_name,
                    reason=reason,
                    details_json=json.dumps(details or {}, ensure_ascii=True, sort_keys=True),
                )
            )
        return risk_gate_event_id

    def list_kill_switch_events(self, limit: int | None = None) -> list[dict]:
        # 全局系统状态，不带 user_id
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

    def get_reconciliation_status(
        self,
        user_id: str,
        run_context_id: str | None = None,
    ) -> dict:
        # user_id 限定用户维度的 execution_orders / account_snapshots；
        # broker_events 是全局表，不带 user_id
        with self.engine.begin() as conn:
            open_orders_stmt = (
                select(func.count())
                .select_from(ExecutionOrderRow)
                .where(ExecutionOrderRow.user_id == user_id)
                .where(ExecutionOrderRow.status != "FILLED")
            )
            broker_events_stmt = select(func.count()).select_from(BrokerEventRow)
            if run_context_id is not None:
                open_orders_stmt = open_orders_stmt.where(ExecutionOrderRow.run_context_id == run_context_id)
                broker_events_stmt = broker_events_stmt.where(BrokerEventRow.run_context_id == run_context_id)
            open_orders = conn.execute(open_orders_stmt).scalar_one()
            broker_event_count = conn.execute(broker_events_stmt).scalar_one()

        snapshot = self.get_latest_account_snapshot(user_id=user_id, run_context_id=run_context_id)
        orders = self.list_execution_orders(user_id=user_id, limit=500, run_context_id=run_context_id)
        fee_by_symbol: dict[str, float] = {}
        order_ids_by_symbol: dict[str, list[str]] = {}
        for order in orders:
            symbol = order["symbol"]
            fee_by_symbol[symbol] = round(fee_by_symbol.get(symbol, 0.0) + float(order.get("fee", 0.0) or 0.0), 2)
            order_ids_by_symbol.setdefault(symbol, []).append(order["execution_order_id"])
        items = []
        if snapshot:
            for symbol, pos in (snapshot.get("positions") or {}).items():
                items.append(
                    {
                        "symbol": symbol,
                        "quantity": int(pos.get("quantity", 0)),
                        "avg_cost": float(pos.get("avg_cost", 0.0)),
                        "mark_price": float(pos.get("mark_price", 0.0)),
                        "market_value": float(pos.get("market_value", 0.0)),
                        "unrealized_pnl": float(pos.get("unrealized_pnl", 0.0)),
                        "change_pct": float(pos.get("change_pct", 0.0)),
                        "fee_total": fee_by_symbol.get(symbol, 0.0),
                        "mark_time": pos.get("mark_time"),
                        "quote_status": pos.get("quote_status", "ok"),
                        "execution_order_ids": order_ids_by_symbol.get(symbol, []),
                    }
                )
        return {
            "open_orders": open_orders,
            "broker_event_count": broker_event_count,
            "healthy": open_orders == 0 or broker_event_count > 0,
            "run_context_id": run_context_id,
            "items": sorted(items, key=lambda item: item["symbol"]),
        }

    def sum_daily_pnl(self, trade_date: str | None = None) -> float:
        # 全局表（HMAC 验签），不带 user_id
        if trade_date:
            cst_today = datetime.fromisoformat(trade_date).replace(tzinfo=_CST)
        else:
            cst_today = datetime.now(_CST)
        day_start_cst = cst_today.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end_cst = day_start_cst + timedelta(days=1)
        day_start = day_start_cst.astimezone(UTC).replace(tzinfo=None)
        day_end = day_end_cst.astimezone(UTC).replace(tzinfo=None)

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
        # 全局系统状态，不带 user_id
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
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def insert_account_snapshot(
        self,
        user_id: str,
        cash: float,
        nav: float,
        positions: dict,
        run_context_id: str | None = None,
    ) -> str:
        snapshot_id = f"acct-{uuid.uuid4().hex[:12]}"
        effective_run_context_id = run_context_id or snapshot_id
        with self.engine.begin() as conn:
            conn.execute(
                AccountSnapshotRow.__table__.insert().values(
                    snapshot_id=snapshot_id,
                    user_id=user_id,
                    cash=cash,
                    nav=nav,
                    run_context_id=effective_run_context_id,
                    positions_json=json.dumps(positions, ensure_ascii=True),
                )
            )
        return snapshot_id

    def get_latest_account_snapshot(
        self,
        user_id: str,
        run_context_id: str | None = None,
    ) -> dict | None:
        with self.engine.begin() as conn:
            stmt = (
                select(AccountSnapshotRow)
                .where(AccountSnapshotRow.user_id == user_id)
                .order_by(AccountSnapshotRow.created_at.desc())
                .limit(1)
            )
            if run_context_id is not None:
                stmt = stmt.where(AccountSnapshotRow.run_context_id == run_context_id)
            row = conn.execute(stmt).fetchone()
        if row is None:
            return None
        return {
            "snapshot_id": row.snapshot_id,
            "cash": row.cash,
            "nav": row.nav,
            "run_context_id": row.run_context_id,
            "positions": json.loads(row.positions_json),
            "created_at": row.created_at.isoformat(),
        }

    def list_account_snapshots(
        self,
        user_id: str,
        since: datetime | None = None,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = (
                select(AccountSnapshotRow)
                .where(AccountSnapshotRow.user_id == user_id)
                .order_by(AccountSnapshotRow.created_at)
            )
            if since is not None:
                stmt = stmt.where(AccountSnapshotRow.created_at >= since)
            rows = conn.execute(stmt).fetchall()
        return [
            {
                "snapshot_id": row.snapshot_id,
                "cash": row.cash,
                "nav": row.nav,
                "positions": json.loads(row.positions_json),
                "created_at": _cst_iso(row.created_at),
            }
            for row in rows
        ]

    def get_preference(self, user_id: str, key: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(UserPreferenceRow).where(
                    UserPreferenceRow.user_id == user_id,
                    UserPreferenceRow.key == key,
                )
            ).fetchone()
        if row is None:
            return None
        return json.loads(row.value)

    def set_preference(self, user_id: str, key: str, value: dict) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(UserPreferenceRow).where(
                    UserPreferenceRow.user_id == user_id,
                    UserPreferenceRow.key == key,
                )
            ).fetchone()
            if existing is not None:
                conn.execute(
                    UserPreferenceRow.__table__.update()
                    .where(
                        UserPreferenceRow.user_id == user_id,
                        UserPreferenceRow.key == key,
                    )
                    .values(value=json.dumps(value, ensure_ascii=True))
                )
            else:
                conn.execute(
                    UserPreferenceRow.__table__.insert().values(
                        user_id=user_id,
                        key=key,
                        value=json.dumps(value, ensure_ascii=True),
                    )
                )

    def insert_alpha_ticket(
        self,
        user_id: str,
        asset_symbol: str,
        underlying_symbol: str,
        action: str,
        thesis: str,
        suggested_quantity: float,
        suggested_limit_price: float,
        expires_at: str,
    ) -> str:
        ticket_id = f"alpha-ticket-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                AlphaTicketRow.__table__.insert().values(
                    ticket_id=ticket_id,
                    user_id=user_id,
                    asset_symbol=asset_symbol,
                    underlying_symbol=underlying_symbol,
                    action=action,
                    thesis=thesis,
                    suggested_quantity=suggested_quantity,
                    suggested_limit_price=suggested_limit_price,
                    expires_at=datetime.fromisoformat(expires_at),
                    status="PROPOSED",
                )
            )
        return ticket_id

    def approve_alpha_ticket(self, user_id: str, ticket_id: str, operator_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                AlphaTicketRow.__table__.update()
                .where(AlphaTicketRow.ticket_id == ticket_id)
                .where(AlphaTicketRow.user_id == user_id)
                .values(status="APPROVED", approved_by=operator_id)
            )

    def insert_alpha_manual_fill(
        self,
        user_id: str,
        ticket_id: str,
        operator_id: str,
        executed_quantity: float,
        executed_price: float,
        notes: str,
        executed_at: str | None = None,
    ) -> str:
        fill_id = f"alpha-fill-{uuid.uuid4().hex[:12]}"
        executed_at_dt = _parse_summary_timestamp(executed_at) or datetime.utcnow()
        with self.engine.begin() as conn:
            conn.execute(
                AlphaManualFillRow.__table__.insert().values(
                    fill_id=fill_id,
                    user_id=user_id,
                    ticket_id=ticket_id,
                    operator_id=operator_id,
                    executed_quantity=executed_quantity,
                    executed_price=executed_price,
                    executed_at=executed_at_dt,
                    notes=notes,
                )
            )
        return fill_id

    def list_alpha_tickets(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaTicketRow)
                .where(AlphaTicketRow.user_id == user_id)
                .order_by(AlphaTicketRow.created_at.desc())
            ).fetchall()
            return [
                {
                    "ticket_id": row.ticket_id,
                    "asset_symbol": row.asset_symbol,
                    "underlying_symbol": row.underlying_symbol,
                    "action": row.action,
                    "thesis": row.thesis,
                    "suggested_quantity": row.suggested_quantity,
                    "suggested_limit_price": row.suggested_limit_price,
                    "status": row.status,
                    "approved_by": row.approved_by,
                    "expires_at": _cst_iso(row.expires_at),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def list_alpha_manual_fills(self, user_id: str, ticket_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaManualFillRow)
                .where(AlphaManualFillRow.user_id == user_id)
                .where(AlphaManualFillRow.ticket_id == ticket_id)
                .order_by(AlphaManualFillRow.executed_at.desc())
            ).fetchall()
            return [
                {
                    "fill_id": row.fill_id,
                    "ticket_id": row.ticket_id,
                    "operator_id": row.operator_id,
                    "executed_quantity": row.executed_quantity,
                    "executed_price": row.executed_price,
                    "executed_at": _cst_iso(row.executed_at),
                    "notes": row.notes,
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def list_all_alpha_manual_fills(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaManualFillRow)
                .where(AlphaManualFillRow.user_id == user_id)
                .order_by(AlphaManualFillRow.executed_at)
            ).fetchall()
            return [
                {
                    "fill_id": row.fill_id,
                    "ticket_id": row.ticket_id,
                    "operator_id": row.operator_id,
                    "executed_quantity": row.executed_quantity,
                    "executed_price": row.executed_price,
                    "executed_at": _cst_iso(row.executed_at),
                    "notes": row.notes,
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def replace_alpha_positions(self, user_id: str, positions: list[dict]) -> None:
        with self.engine.begin() as conn:
            # 只删除该用户的持仓
            conn.execute(
                AlphaPositionRow.__table__.delete().where(AlphaPositionRow.user_id == user_id)
            )
            for position in positions:
                conn.execute(
                    AlphaPositionRow.__table__.insert().values(
                        user_id=user_id,
                        symbol=position["symbol"],
                        quantity=position["quantity"],
                        avg_cost=position["avg_cost"],
                        mark_price=position["mark_price"],
                    )
                )

    def list_alpha_positions(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaPositionRow)
                .where(AlphaPositionRow.user_id == user_id)
                .order_by(AlphaPositionRow.symbol)
            ).fetchall()
            return [
                {
                    "symbol": row.symbol,
                    "quantity": row.quantity,
                    "avg_cost": row.avg_cost,
                    "mark_price": row.mark_price,
                    "updated_at": _cst_iso(row.updated_at),
                }
                for row in rows
            ]

    def insert_alpha_portfolio_snapshot(
        self,
        user_id: str,
        cash_balance: float,
        realized_pnl: float,
        unrealized_pnl: float,
        nav: float,
    ) -> str:
        snapshot_id = f"alpha-snap-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                AlphaPortfolioSnapshotRow.__table__.insert().values(
                    snapshot_id=snapshot_id,
                    user_id=user_id,
                    cash_balance=cash_balance,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized_pnl,
                    nav=nav,
                )
            )
        return snapshot_id

    def get_latest_alpha_portfolio_snapshot(self, user_id: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(AlphaPortfolioSnapshotRow)
                .where(AlphaPortfolioSnapshotRow.user_id == user_id)
                .order_by(AlphaPortfolioSnapshotRow.created_at.desc())
                .limit(1)
            ).one_or_none()
            if row is None:
                return None
            return {
                "snapshot_id": row.snapshot_id,
                "cash_balance": row.cash_balance,
                "realized_pnl": row.realized_pnl,
                "unrealized_pnl": row.unrealized_pnl,
                "nav": row.nav,
                "created_at": _cst_iso(row.created_at),
            }

    def insert_alpha_reconciliation_run(
        self,
        user_id: str,
        source: str,
        status: str,
        discrepancies: dict,
    ) -> str:
        run_id = f"alpha-recon-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                AlphaReconciliationRunRow.__table__.insert().values(
                    run_id=run_id,
                    user_id=user_id,
                    source=source,
                    status=status,
                    discrepancies_json=json.dumps(discrepancies, ensure_ascii=True, sort_keys=True),
                )
            )
        return run_id

    def list_alpha_reconciliation_runs(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaReconciliationRunRow)
                .where(AlphaReconciliationRunRow.user_id == user_id)
                .order_by(AlphaReconciliationRunRow.created_at.desc())
            ).fetchall()
            return [
                {
                    "run_id": row.run_id,
                    "source": row.source,
                    "status": row.status,
                    "discrepancies": json.loads(row.discrepancies_json),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def add_alpha_watchlist_item(self, symbol: str, underlying_symbol: str, priority: int) -> None:
        # Watchlist 由 Worktree 2 维护，这里保留兼容
        with self.engine.begin() as conn:
            conn.execute(
                AlphaWatchlistItemRow.__table__.insert().values(
                    symbol=symbol,
                    underlying_symbol=underlying_symbol,
                    priority=priority,
                )
            )

    def remove_alpha_watchlist_item(self, symbol: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                AlphaWatchlistItemRow.__table__.delete().where(AlphaWatchlistItemRow.symbol == symbol)
            )

    def list_alpha_watchlist_items(self) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaWatchlistItemRow).order_by(AlphaWatchlistItemRow.priority, AlphaWatchlistItemRow.symbol)
            ).fetchall()
            return [
                {
                    "symbol": row.symbol,
                    "underlying_symbol": row.underlying_symbol,
                    "priority": row.priority,
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def insert_alpha_api_order_attempt(
        self,
        user_id: str,
        ticket_id: str,
        asset_symbol: str,
        action: str,
        quantity: float,
        limit_price: float,
        mode: str,
        status: str,
        remote_order_id: str | None,
        response_payload: dict,
    ) -> str:
        attempt_id = f"alpha-api-order-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                AlphaApiOrderAttemptRow.__table__.insert().values(
                    attempt_id=attempt_id,
                    user_id=user_id,
                    ticket_id=ticket_id,
                    asset_symbol=asset_symbol,
                    action=action,
                    quantity=quantity,
                    limit_price=limit_price,
                    mode=mode,
                    status=status,
                    remote_order_id=remote_order_id,
                    response_payload_json=json.dumps(response_payload, ensure_ascii=True, sort_keys=True),
                )
            )
        return attempt_id

    def list_alpha_api_order_attempts(self, user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(AlphaApiOrderAttemptRow)
                .where(AlphaApiOrderAttemptRow.user_id == user_id)
                .order_by(AlphaApiOrderAttemptRow.created_at.desc())
            ).fetchall()
            return [
                {
                    "attempt_id": row.attempt_id,
                    "ticket_id": row.ticket_id,
                    "asset_symbol": row.asset_symbol,
                    "action": row.action,
                    "quantity": row.quantity,
                    "limit_price": row.limit_price,
                    "mode": row.mode,
                    "status": row.status,
                    "remote_order_id": row.remote_order_id,
                    "response_payload": json.loads(row.response_payload_json),
                    "created_at": _cst_iso(row.created_at),
                }
                for row in rows
            ]

    def upsert_dashboard_run_summary(
        self,
        user_id: str,
        run_context_id: str,
        trade_date: str,
        decision_mode: str,
        execution_mode: str,
        capital_base: int,
        status: str,
        execution_fee_total: float,
        realized_pnl: float,
        unrealized_pnl: float,
        net_pnl: float,
        started_at: str,
        finished_at: str | None,
        latest_workbench: dict,
    ) -> None:
        values = {
            "run_context_id": run_context_id,
            "user_id": user_id,
            "trade_date": trade_date,
            "decision_mode": decision_mode,
            "execution_mode": execution_mode,
            "capital_base": capital_base,
            "status": status,
            "execution_fee_total": execution_fee_total,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
            "started_at": _parse_summary_timestamp(started_at),
            "finished_at": _parse_summary_timestamp(finished_at),
            "latest_workbench_json": json.dumps(latest_workbench, ensure_ascii=True, sort_keys=True),
            "updated_at": datetime.utcnow(),
        }
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(DashboardRunSummaryRow)
                .where(DashboardRunSummaryRow.run_context_id == run_context_id)
                .where(DashboardRunSummaryRow.user_id == user_id)
            ).fetchone()
            if existing is None:
                conn.execute(
                    DashboardRunSummaryRow.__table__.insert().values(
                        created_at=datetime.utcnow(), **values
                    )
                )
            else:
                conn.execute(
                    DashboardRunSummaryRow.__table__.update()
                    .where(DashboardRunSummaryRow.run_context_id == run_context_id)
                    .where(DashboardRunSummaryRow.user_id == user_id)
                    .values(**values)
                )

    def get_dashboard_run_summary(self, user_id: str, run_context_id: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(DashboardRunSummaryRow)
                .where(DashboardRunSummaryRow.run_context_id == run_context_id)
                .where(DashboardRunSummaryRow.user_id == user_id)
            ).fetchone()
        if row is None:
            return None
        return {
            "run_context_id": row.run_context_id,
            "trade_date": row.trade_date,
            "decision_mode": row.decision_mode,
            "execution_mode": row.execution_mode,
            "capital_base": row.capital_base,
            "status": row.status,
            "execution_fee_total": row.execution_fee_total,
            "realized_pnl": row.realized_pnl,
            "unrealized_pnl": row.unrealized_pnl,
            "net_pnl": row.net_pnl,
            "started_at": _cst_iso(row.started_at),
            "finished_at": _cst_iso(row.finished_at) if row.finished_at else None,
            "latest_workbench": json.loads(row.latest_workbench_json or "{}"),
        }

    def list_dashboard_run_summaries(self, user_id: str, limit: int = 50) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(DashboardRunSummaryRow)
                .where(DashboardRunSummaryRow.user_id == user_id)
                .order_by(DashboardRunSummaryRow.started_at.desc(), DashboardRunSummaryRow.run_context_id.desc())
                .limit(limit)
            ).fetchall()
        return [
            {
                "run_context_id": row.run_context_id,
                "trade_date": row.trade_date,
                "decision_mode": row.decision_mode,
                "execution_mode": row.execution_mode,
                "capital_base": row.capital_base,
                "status": row.status,
                "execution_fee_total": row.execution_fee_total,
                "realized_pnl": row.realized_pnl,
                "unrealized_pnl": row.unrealized_pnl,
                "net_pnl": row.net_pnl,
                "started_at": _cst_iso(row.started_at),
                "finished_at": _cst_iso(row.finished_at) if row.finished_at else None,
                "created_at": _cst_iso(row.created_at),
                "updated_at": _cst_iso(row.updated_at),
                "latest_workbench": json.loads(row.latest_workbench_json or "{}"),
            }
            for row in rows
        ]

    def append_dashboard_run_event(
        self,
        user_id: str,
        run_context_id: str,
        event_type: str,
        stage: str,
        status: str,
        payload: dict,
    ) -> int:
        event_id = f"dre-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            current_seq = conn.execute(
                select(func.max(DashboardRunEventRow.seq))
                .where(DashboardRunEventRow.run_context_id == run_context_id)
                .where(DashboardRunEventRow.user_id == user_id)
            ).scalar_one()
            next_seq = int(current_seq or 0) + 1
            conn.execute(
                DashboardRunEventRow.__table__.insert().values(
                    event_id=event_id,
                    user_id=user_id,
                    run_context_id=run_context_id,
                    seq=next_seq,
                    event_type=event_type,
                    stage=stage,
                    status=status,
                    payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                )
            )
        return next_seq

    def list_dashboard_run_events(
        self,
        user_id: str,
        run_context_id: str,
        after_seq: int = 0,
    ) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(DashboardRunEventRow)
                .where(DashboardRunEventRow.user_id == user_id)
                .where(DashboardRunEventRow.run_context_id == run_context_id)
                .where(DashboardRunEventRow.seq > after_seq)
                .order_by(DashboardRunEventRow.seq.asc())
            ).fetchall()
        return [
            {
                "run_context_id": row.run_context_id,
                "seq": row.seq,
                "event_type": row.event_type,
                "stage": row.stage,
                "status": row.status,
                "payload": json.loads(row.payload_json or "{}"),
                "created_at": _cst_iso(row.created_at),
            }
            for row in rows
        ]
