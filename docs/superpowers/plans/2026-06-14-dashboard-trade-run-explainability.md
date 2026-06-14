# Dashboard Trade Run Explainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard trading run show stock-level reconciliation, target-failure reasons, order lifecycle, traceable IDs, and precise quote/timing metadata in one canonical backend-driven flow.

**Architecture:** Keep `POST /api/v1/dashboard/run` and `GET /api/v1/dashboard/workbench` as the only authoritative path. Persist run-scoped IDs, target diagnostics, richer execution-order lifecycle fields, and stock-level reconciliation snapshots in the existing runtime-store tables, then let the dashboard render those backend fields directly instead of inferring missing business state in JavaScript. Use Alembic for schema changes so the existing PostgreSQL deployment upgrades cleanly.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, plain Python services, vanilla HTML/CSS/JS, pytest

---

## Scope Check

These six issues belong to one subsystem: the shadow-trading run observability path. Keep this as one plan so storage fields, API contracts, and UI labels land in one pass; do not split it into separate partial plans that would create incompatible data shapes for target rows, order rows, and reconciliation rows.

## File Structure

- Create: `alembic/versions/20260614_000010_add_dashboard_trade_run_explainability.py`
  Add the new run-scoped columns and lifecycle/detail columns needed by the dashboard.
- Modify: `src/storage/models.py`
  Add the canonical SQLAlchemy fields for run context, target diagnostics, order lifecycle, and enriched reconciliation snapshots.
- Modify: `src/storage/runtime_store.py`
  Persist and query the new fields; expose run-scoped target/order/snapshot reads for the dashboard.
- Modify: `src/portfolio/target_planner.py`
  Keep zero-quantity target attempts instead of dropping them; surface lot-size diagnostics and raw-versus-rounded quantity.
- Modify: `src/risk/pre_trade_risk.py`
  Return structured risk-gate details so blocked targets can explain exactly why they did not become orders.
- Modify: `src/execution/paper_execution_service.py`
  Persist lifecycle timestamps, partial/full fill metadata, and stock-level reconciliation snapshot data for the current run.
- Modify: `src/api/routes_dashboard.py`
  Build the enriched `latest_run`, `history.targets`, `history.orders`, and `history.reconcile` payloads; attach durations and quote timestamps to each stage.
- Modify: `src/api/routes_reconciliation.py`
  Return the same stock-level reconciliation rows as the dashboard, with optional `run_context_id` filtering.
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
  Add a reconciliation tab and widen target/order tables so the new fields are visible.
- Modify: `src/api/dashboard_page/scripts/dashboard.js`
  Render stock-level reconciliation rows, target failure reasons, order lifecycle fields, and per-stage durations without frontend-side business inference.
- Modify: `src/api/dashboard_page/styles/dashboard.css`
  Add the small table/layout rules needed for the wider history tables and trace cells.
- Modify: `tests/test_runtime_store_pg.py`
  Cover new runtime-store persistence and run-scoped query behavior.
- Modify: `tests/test_target_planner.py`
  Cover zero-quantity target attempts and lot-size diagnostics.
- Modify: `tests/test_risk_gate.py`
  Cover structured risk-gate detail payloads.
- Modify: `tests/test_paper_execution_service.py`
  Cover lifecycle timestamps and reconciliation snapshot enrichment.
- Modify: `tests/test_dashboard_api.py`
  Lock the API contract for target reasons, order lifecycle rows, reconciliation rows, and stage durations.
- Modify: `tests/test_dashboard_page_contract.py`
  Lock the new HTML markers for the reconciliation tab and trace-aware tables.
- Modify: `docs/sop.md`
  Explain how to read the new target, order, and reconciliation sections as a beginner.

### Task 1: Add Run-Scoped Storage And Migration

**Files:**
- Create: `alembic/versions/20260614_000010_add_dashboard_trade_run_explainability.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_runtime_store_pg.py`

- [ ] **Step 1: Write the failing storage test**

```python
# tests/test_runtime_store_pg.py
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_lists_run_scoped_target_order_and_snapshot_details(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="dashboard-wrk-001",
        run_context_id="wrk-001",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="seed decision",
        input_snapshot={"symbol": "600519.SH"},
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        run_context_id="wrk-001",
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        target_position_ratio=0.1,
        expires_at="2026-12-31T10:15:00",
        status="BLOCKED",
        status_reason="cash",
        price=102.5,
        lot_size=100,
        requested_quantity=975.61,
        notional=92250,
        diagnostics={"available_cash": 50000.0, "raw_quantity": 975.61},
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        run_context_id="wrk-001",
        symbol="600519.SH",
        action="BUY",
        quantity=900,
        limit_price=102.5,
        status="PARTIAL",
        status_code="PARTIALLY_FILLED",
        status_reason="first_fill",
        submitted_at="2026-06-14T10:00:00+08:00",
        slippage_bps=5.0,
    )
    store.update_execution_order_status(
        execution_order_id,
        status="PARTIAL",
        status_code="PARTIALLY_FILLED",
        status_reason="400/900 filled",
        filled_quantity=400,
        fill_price=102.55,
        fee=12.31,
        pnl_delta=0.0,
        last_event_at="2026-06-14T10:00:02+08:00",
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        run_context_id="wrk-001",
        event_id="evt-001",
        event_type="PARTIALLY_FILLED",
        payload={"filled_quantity": 400},
    )
    store.insert_account_snapshot(
        cash=950000.0,
        nav=990500.0,
        run_context_id="wrk-001",
        positions={
            "600519.SH": {
                "quantity": 400,
                "avg_cost": 102.55,
                "mark_price": 103.10,
                "market_value": 41240.0,
                "unrealized_pnl": 220.0,
                "change_pct": 0.0054,
                "mark_time": "2026-06-14T10:00:03+08:00",
            }
        },
    )

    targets = store.list_target_positions(run_context_id="wrk-001")
    orders = store.list_execution_orders(run_context_id="wrk-001")
    reconcile = store.get_reconciliation_status(run_context_id="wrk-001")

    assert targets[0]["status_reason"] == "cash"
    assert targets[0]["diagnostics"]["available_cash"] == 50000.0
    assert orders[0]["status_code"] == "PARTIALLY_FILLED"
    assert orders[0]["filled_quantity"] == 400
    assert reconcile["items"][0]["mark_price"] == 103.10
```

- [ ] **Step 2: Run the storage test to confirm it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py::test_runtime_store_lists_run_scoped_target_order_and_snapshot_details -v
```

Expected:

- `TypeError` because `insert_decision_run`, `insert_target_position`, `insert_execution_order`, or `insert_account_snapshot` do not accept the new keyword arguments
- `AttributeError` because `list_target_positions` does not exist yet

- [ ] **Step 3: Add the migration, model fields, and runtime-store methods**

```python
# alembic/versions/20260614_000010_add_dashboard_trade_run_explainability.py
from alembic import op
import sqlalchemy as sa


revision = "20260614_000010"
down_revision = "20260607_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decision_runs", sa.Column("run_context_id", sa.String(length=64), nullable=True))
    op.add_column("target_positions", sa.Column("run_context_id", sa.String(length=64), nullable=True))
    op.add_column("target_positions", sa.Column("status_reason", sa.String(length=64), nullable=False, server_default="ready"))
    op.add_column("target_positions", sa.Column("price", sa.Float(), nullable=False, server_default="0"))
    op.add_column("target_positions", sa.Column("lot_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_positions", sa.Column("requested_quantity", sa.Float(), nullable=False, server_default="0"))
    op.add_column("target_positions", sa.Column("notional", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_positions", sa.Column("diagnostics_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("execution_orders", sa.Column("run_context_id", sa.String(length=64), nullable=True))
    op.add_column("execution_orders", sa.Column("filled_quantity", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("execution_orders", sa.Column("fill_price", sa.Float(), nullable=True))
    op.add_column("execution_orders", sa.Column("fee", sa.Float(), nullable=False, server_default="0"))
    op.add_column("execution_orders", sa.Column("pnl_delta", sa.Float(), nullable=False, server_default="0"))
    op.add_column("execution_orders", sa.Column("status_code", sa.String(length=32), nullable=False, server_default="READY"))
    op.add_column("execution_orders", sa.Column("status_reason", sa.String(length=128), nullable=False, server_default="ready"))
    op.add_column("execution_orders", sa.Column("slippage_bps", sa.Float(), nullable=False, server_default="0"))
    op.add_column("execution_orders", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    op.add_column("execution_orders", sa.Column("filled_at", sa.DateTime(), nullable=True))
    op.add_column("execution_orders", sa.Column("last_event_at", sa.DateTime(), nullable=True))
    op.add_column("broker_events", sa.Column("run_context_id", sa.String(length=64), nullable=True))
    op.add_column("risk_gate_events", sa.Column("run_context_id", sa.String(length=64), nullable=True))
    op.add_column("risk_gate_events", sa.Column("target_position_id", sa.String(length=64), nullable=True))
    op.add_column("risk_gate_events", sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("account_snapshots", sa.Column("run_context_id", sa.String(length=64), nullable=True))

    op.execute("UPDATE decision_runs SET run_context_id = decision_run_id WHERE run_context_id IS NULL")
    op.execute(
        """
        UPDATE target_positions AS tp
        SET run_context_id = dr.run_context_id
        FROM decision_runs AS dr
        WHERE tp.decision_run_id = dr.decision_run_id AND tp.run_context_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE execution_orders AS eo
        SET run_context_id = tp.run_context_id
        FROM target_positions AS tp
        WHERE eo.target_position_id = tp.target_position_id AND eo.run_context_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE broker_events AS be
        SET run_context_id = eo.run_context_id
        FROM execution_orders AS eo
        WHERE be.order_id = eo.execution_order_id AND be.run_context_id IS NULL
        """
    )
    op.execute("UPDATE account_snapshots SET run_context_id = snapshot_id WHERE run_context_id IS NULL")

    op.alter_column("decision_runs", "run_context_id", nullable=False)
    op.alter_column("target_positions", "run_context_id", nullable=False)
    op.alter_column("execution_orders", "run_context_id", nullable=False)
    op.alter_column("broker_events", "run_context_id", nullable=False)
    op.alter_column("risk_gate_events", "run_context_id", nullable=False)
    op.alter_column("account_snapshots", "run_context_id", nullable=False)

    op.create_index("ix_decision_runs_run_context_id", "decision_runs", ["run_context_id"])
    op.create_index("ix_target_positions_run_context_id", "target_positions", ["run_context_id"])
    op.create_index("ix_execution_orders_run_context_id", "execution_orders", ["run_context_id"])
    op.create_index("ix_broker_events_run_context_id", "broker_events", ["run_context_id"])
    op.create_index("ix_account_snapshots_run_context_id", "account_snapshots", ["run_context_id"])


def downgrade() -> None:
    op.drop_index("ix_account_snapshots_run_context_id", table_name="account_snapshots")
    op.drop_index("ix_broker_events_run_context_id", table_name="broker_events")
    op.drop_index("ix_execution_orders_run_context_id", table_name="execution_orders")
    op.drop_index("ix_target_positions_run_context_id", table_name="target_positions")
    op.drop_index("ix_decision_runs_run_context_id", table_name="decision_runs")

    op.drop_column("account_snapshots", "run_context_id")
    op.drop_column("risk_gate_events", "details_json")
    op.drop_column("risk_gate_events", "target_position_id")
    op.drop_column("risk_gate_events", "run_context_id")
    op.drop_column("broker_events", "run_context_id")
    op.drop_column("execution_orders", "last_event_at")
    op.drop_column("execution_orders", "filled_at")
    op.drop_column("execution_orders", "submitted_at")
    op.drop_column("execution_orders", "slippage_bps")
    op.drop_column("execution_orders", "status_reason")
    op.drop_column("execution_orders", "status_code")
    op.drop_column("execution_orders", "pnl_delta")
    op.drop_column("execution_orders", "fee")
    op.drop_column("execution_orders", "fill_price")
    op.drop_column("execution_orders", "filled_quantity")
    op.drop_column("execution_orders", "run_context_id")
    op.drop_column("target_positions", "diagnostics_json")
    op.drop_column("target_positions", "notional")
    op.drop_column("target_positions", "requested_quantity")
    op.drop_column("target_positions", "lot_size")
    op.drop_column("target_positions", "price")
    op.drop_column("target_positions", "status_reason")
    op.drop_column("target_positions", "run_context_id")
    op.drop_column("decision_runs", "run_context_id")
```

```python
# src/storage/models.py
class DecisionRunRow(Base):
    __tablename__ = "decision_runs"

    decision_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    ...


class TargetPositionRow(Base):
    __tablename__ = "target_positions"

    target_position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    target_position_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    status_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notional: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ...


class ExecutionOrderRow(Base):
    __tablename__ = "execution_orders"

    execution_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_position_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pnl_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="READY")
    status_code: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    status_reason: Mapped[str] = mapped_column(String(128), nullable=False, default="ready")
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BrokerEventRow(Base):
    __tablename__ = "broker_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ...


class RiskGateEventRow(Base):
    __tablename__ = "risk_gate_events"

    risk_gate_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_position_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AccountSnapshotRow(Base):
    __tablename__ = "account_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    positions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/storage/runtime_store.py
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


def insert_target_position(
    self,
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
            select(DecisionRunRow.run_context_id).where(DecisionRunRow.decision_run_id == decision_run_id)
        ).scalar_one()
        conn.execute(
            TargetPositionRow.__table__.insert().values(
                target_position_id=target_position_id,
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


def list_target_positions(
    self,
    limit: int | None = None,
    offset: int = 0,
    run_context_id: str | None = None,
) -> list[dict]:
    with self.engine.begin() as conn:
        stmt = select(TargetPositionRow).order_by(TargetPositionRow.created_at.desc())
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


def insert_execution_order(
    self,
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
            select(TargetPositionRow.run_context_id).where(TargetPositionRow.target_position_id == target_position_id)
        ).scalar_one()
        conn.execute(
            ExecutionOrderRow.__table__.insert().values(
                execution_order_id=execution_order_id,
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


def update_execution_order_status(
    self,
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
            .values(**values)
        )


def list_execution_orders(
    self,
    limit: int | None = None,
    offset: int = 0,
    run_context_id: str | None = None,
) -> list[dict]:
    with self.engine.begin() as conn:
        stmt = select(ExecutionOrderRow).order_by(ExecutionOrderRow.created_at.desc())
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


def insert_broker_order_event(
    self,
    execution_order_id: str,
    event_id: str,
    event_type: str,
    payload: dict,
    run_context_id: str | None = None,
) -> None:
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


def insert_risk_gate_event(
    self,
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


def insert_account_snapshot(self, cash: float, nav: float, positions: dict, run_context_id: str | None = None) -> str:
    snapshot_id = f"acct-{uuid.uuid4().hex[:12]}"
    effective_run_context_id = run_context_id or snapshot_id
    with self.engine.begin() as conn:
        conn.execute(
            AccountSnapshotRow.__table__.insert().values(
                snapshot_id=snapshot_id,
                cash=cash,
                nav=nav,
                run_context_id=effective_run_context_id,
                positions_json=json.dumps(positions, ensure_ascii=True),
            )
        )
    return snapshot_id


def get_latest_account_snapshot(self, run_context_id: str | None = None) -> dict | None:
    with self.engine.begin() as conn:
        stmt = select(AccountSnapshotRow).order_by(AccountSnapshotRow.created_at.desc()).limit(1)
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


def get_reconciliation_status(self, run_context_id: str | None = None) -> dict:
    with self.engine.begin() as conn:
        open_orders_stmt = select(func.count()).select_from(ExecutionOrderRow).where(ExecutionOrderRow.status != "FILLED")
        broker_events_stmt = select(func.count()).select_from(BrokerEventRow)
        if run_context_id is not None:
            open_orders_stmt = open_orders_stmt.where(ExecutionOrderRow.run_context_id == run_context_id)
            broker_events_stmt = broker_events_stmt.where(BrokerEventRow.run_context_id == run_context_id)
        open_orders = conn.execute(open_orders_stmt).scalar_one()
        broker_event_count = conn.execute(broker_events_stmt).scalar_one()

    snapshot = self.get_latest_account_snapshot(run_context_id=run_context_id)
    orders = self.list_execution_orders(limit=500, run_context_id=run_context_id)
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
```

- [ ] **Step 4: Run the focused storage checks and migration**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py::test_runtime_store_lists_run_scoped_target_order_and_snapshot_details -v
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

Expected:

- The pytest case passes
- Alembic prints `Running upgrade 20260607_000009 -> 20260614_000010`

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add alembic/versions/20260614_000010_add_dashboard_trade_run_explainability.py src/storage/models.py src/storage/runtime_store.py tests/test_runtime_store_pg.py
git commit -m "feat: add run-scoped dashboard trade detail storage"
```

### Task 2: Keep Target Attempts And Risk Diagnostics Instead Of Dropping Them

**Files:**
- Modify: `src/portfolio/target_planner.py`
- Modify: `src/risk/pre_trade_risk.py`
- Test: `tests/test_target_planner.py`
- Test: `tests/test_risk_gate.py`

- [ ] **Step 1: Write the failing planner and risk tests**

```python
# tests/test_target_planner.py
from src.portfolio.target_planner import build_target_positions


def test_build_target_positions_keeps_zero_quantity_buy_with_diagnostics():
    targets = build_target_positions(
        decisions=[{"symbol": "600519.SH", "action": "BUY"}],
        prices={"600519.SH": 2000.0},
        capital_base=10_000,
        max_position_ratio=0.2,
        lot_size_a=100,
        current_positions={},
    )

    assert len(targets) == 1
    assert targets[0]["quantity"] == 0
    assert targets[0]["lot_size"] == 100
    assert targets[0]["raw_quantity"] == 1.0
    assert targets[0]["rounding_loss_quantity"] == 1.0
```

```python
# tests/test_risk_gate.py
from src.risk.pre_trade_risk import evaluate_risk_gate


def test_insufficient_cash_returns_structured_details():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=50_000,
        requested_value=100_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "cash"
    assert result["details"]["available_cash"] == 50_000
    assert result["details"]["requested_value"] == 100_000
```

- [ ] **Step 2: Run the planner and risk tests to confirm they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py::test_build_target_positions_keeps_zero_quantity_buy_with_diagnostics tests/test_risk_gate.py::test_insufficient_cash_returns_structured_details -v
```

Expected:

- `AssertionError` because zero-quantity targets are currently filtered out
- `KeyError` because `details` is not returned from `evaluate_risk_gate`

- [ ] **Step 3: Implement target diagnostics and structured risk details**

```python
# src/portfolio/target_planner.py
def build_target_position(
    symbol: str,
    action: str,
    capital_base: float,
    max_position_ratio: float,
    watchlist_size: int,
    price: float,
    lot_size: int = 0,
    lot_size_a: int = 100,
    lot_size_us: int = 1,
    current_quantity: int = 0,
    expires_at: str = "",
    market: str | None = None,
) -> dict[str, Any]:
    ...
    if action == "BUY":
        target_position_ratio = max_position_ratio / watchlist_size
        target_value = int(capital_base * target_position_ratio)
        raw_quantity = round(target_value / price, 4) if price > 0 else 0.0
        quantity = calculate_lot_quantity(target_value, price, resolved_lot_size)
        rounding_loss_quantity = round(max(raw_quantity - quantity, 0.0), 4)
        notional = int(quantity * price)
    elif action == "SELL":
        target_position_ratio = 0.0
        target_value = 0
        raw_quantity = float(max(int(current_quantity), 0))
        quantity = max(int(current_quantity), 0)
        rounding_loss_quantity = 0.0
        notional = int(quantity * price)
    else:
        target_position_ratio = 0.0
        target_value = 0
        raw_quantity = 0.0
        quantity = 0
        rounding_loss_quantity = 0.0
        notional = 0

    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
        "target_position_ratio": target_position_ratio,
        "raw_quantity": raw_quantity,
        "rounding_loss_quantity": rounding_loss_quantity,
        "quantity": quantity,
        "notional": notional,
        "price": price,
        "lot_size": resolved_lot_size,
        "expires_at": expires_at,
    }


def build_target_positions(...):
    active_decisions = [row for row in decisions if row.get("action") in {"BUY", "SELL"}]
    watchlist_size = max(len(decisions), 1)
    targets = []
    for row in active_decisions:
        ...
        targets.append(target)
    return targets
```

```python
# src/risk/pre_trade_risk.py
def _blocked(rule_name: str, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"approved": False, "rule_name": rule_name, "reason": reason, "details": details}


def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
    current_position_value: float,
    nav: float,
    max_position_ratio: float,
    quantity: int,
    lot_size: int,
    market: str = "CN_A",
    buy_date: date | None = None,
    trade_date: date | None = None,
) -> dict[str, Any]:
    details = {
        "symbol": symbol,
        "action": action,
        "available_cash": available_cash,
        "requested_value": requested_value,
        "current_position_value": current_position_value,
        "nav": nav,
        "max_position_ratio": max_position_ratio,
        "quantity": quantity,
        "lot_size": lot_size,
        "market": market,
        "buy_date": buy_date.isoformat() if buy_date else None,
        "trade_date": trade_date.isoformat() if trade_date else None,
    }
    if kill_switch:
        return _blocked("kill_switch", "kill switch enabled", details)
    if action not in {"BUY", "SELL"}:
        return _blocked("action", "action must be BUY or SELL", details)
    if not is_valid_lot_quantity(action, quantity, lot_size):
        return _blocked("lot_size", "invalid quantity for market lot rule", details)
    if action == "BUY" and requested_value <= 0:
        return _blocked("request_value", "invalid request amount", details)
    if action == "BUY" and requested_value > available_cash:
        return _blocked("cash", "insufficient cash", details)
    if action == "BUY" and nav > 0:
        next_position_ratio = (current_position_value + requested_value) / nav
        if next_position_ratio > max_position_ratio:
            details["next_position_ratio"] = next_position_ratio
            return _blocked("max_position_ratio", "position limit exceeded", details)
    if action == "SELL":
        effective_trade_date = trade_date or date.today()
        if not is_sell_allowed(market, buy_date, effective_trade_date):
            details["trade_date"] = effective_trade_date.isoformat()
            return _blocked("t_plus_one", "same-day A-share sell blocked", details)
    return {"approved": True, "rule_name": "approved", "reason": "approved", "details": details}
```

- [ ] **Step 4: Run the planner and risk tests to confirm they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_risk_gate.py -q
```

Expected: all tests in both files pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/portfolio/target_planner.py src/risk/pre_trade_risk.py tests/test_target_planner.py tests/test_risk_gate.py
git commit -m "feat: keep target attempts and risk diagnostics"
```

### Task 3: Persist Order Lifecycle And Stock-Level Reconciliation Snapshots

**Files:**
- Modify: `src/execution/paper_execution_service.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_paper_execution_service.py`

- [ ] **Step 1: Write the failing execution-service test**

```python
# tests/test_paper_execution_service.py
from sqlalchemy import create_engine

from src.execution.paper_execution_service import PaperExecutionService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_paper_execution_service_records_lifecycle_and_reconcile_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    result = service.execute_targets(
        targets=[
            {
                "run_context_id": "wrk-001",
                "target_position_id": "tp-001",
                "symbol": "600519.SH",
                "action": "BUY",
                "quantity": 100,
                "price": 100.0,
                "notional": 10_000,
            }
        ],
        initial_state={"cash": 1_000_000.0, "positions": {}},
        mark_prices={"600519.SH": 101.0},
        quote_meta_by_symbol={
            "600519.SH": {
                "price": 101.0,
                "as_of": "2026-06-14T10:00:03+08:00",
                "status": "ok",
            }
        },
        trade_date="2026-06-14",
    )

    order = store.list_execution_orders(run_context_id="wrk-001", limit=1)[0]
    snapshot = store.get_latest_account_snapshot(run_context_id="wrk-001")

    assert result["status"] == "ok"
    assert order["status_code"] == "FILLED"
    assert order["filled_quantity"] == 100
    assert order["submitted_at"] is not None
    assert order["filled_at"] is not None
    assert snapshot["positions"]["600519.SH"]["mark_price"] == 101.0
    assert snapshot["positions"]["600519.SH"]["unrealized_pnl"] > 0
```

- [ ] **Step 2: Run the execution-service test to confirm it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_execution_service.py::test_paper_execution_service_records_lifecycle_and_reconcile_snapshot -v
```

Expected:

- `TypeError` because `quote_meta_by_symbol` is not accepted
- `KeyError` because the stored order row does not include `status_code`, `filled_quantity`, or `submitted_at`

- [ ] **Step 3: Implement lifecycle timestamps and snapshot enrichment**

```python
# src/execution/paper_execution_service.py
from datetime import datetime, timezone, timedelta

_CST = timezone(timedelta(hours=8))


def _now_cst_iso() -> str:
    return datetime.now(_CST).isoformat()


class PaperExecutionService:
    ...
    def execute_targets(
        self,
        targets: list[dict[str, Any]],
        initial_state: dict,
        mark_prices: dict[str, float],
        quote_meta_by_symbol: dict[str, dict[str, Any]] | None = None,
        trade_date: str = "",
    ) -> dict[str, Any]:
        state = {"cash": float(initial_state["cash"]), "positions": dict(initial_state.get("positions", {}))}
        order_items = []

        for target in targets:
            action = target["action"]
            price = float(target["price"])
            fill_price = self._fill_price(action, price)
            quantity = int(target["quantity"])
            notional = quantity * fill_price
            fee = round(notional * self.fee_bps / 10_000, 2)
            submitted_at = _now_cst_iso()

            execution_order_id = self.store.insert_execution_order(
                target_position_id=target["target_position_id"],
                run_context_id=target["run_context_id"],
                symbol=target["symbol"],
                action=action,
                quantity=quantity,
                limit_price=price,
                status="SUBMITTED",
                status_code="SUBMITTED",
                status_reason="paper_submitted",
                submitted_at=submitted_at,
                slippage_bps=self.slippage_bps,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                run_context_id=target["run_context_id"],
                event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
                event_type="SUBMITTED",
                payload={"source": "paper", "trade_date": trade_date, "submitted_at": submitted_at},
            )

            fill_state = apply_fill(
                state=state,
                symbol=target["symbol"],
                side=action,
                quantity=quantity,
                price=fill_price,
                fee=fee,
                trade_date=trade_date,
            )
            state = {"cash": fill_state["cash"], "positions": fill_state["positions"]}
            pnl_delta = fill_state["realized_pnl"]
            filled_at = _now_cst_iso()
            self.store.update_execution_order_status(
                execution_order_id,
                status="FILLED",
                status_code="FILLED",
                status_reason="paper_filled",
                filled_quantity=quantity,
                fill_price=fill_price,
                fee=fee,
                pnl_delta=pnl_delta,
                filled_at=filled_at,
                last_event_at=filled_at,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                run_context_id=target["run_context_id"],
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={
                    "source": "paper",
                    "trade_date": trade_date,
                    "fill_price": fill_price,
                    "filled_quantity": quantity,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                    "filled_at": filled_at,
                },
            )
            order_items.append(
                {
                    "execution_order_id": execution_order_id,
                    "target_position_id": target["target_position_id"],
                    "run_context_id": target["run_context_id"],
                    "symbol": target["symbol"],
                    "action": action,
                    "quantity": quantity,
                    "filled_quantity": quantity,
                    "limit_price": price,
                    "fill_price": fill_price,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                    "status": "FILLED",
                    "status_code": "FILLED",
                    "status_reason": "paper_filled",
                    "submitted_at": submitted_at,
                    "filled_at": filled_at,
                }
            )

        nav = compute_nav(state, mark_prices)
        positions = self._decorate_positions(state["positions"], mark_prices, quote_meta_by_symbol or {})
        snapshot_id = self.store.insert_account_snapshot(
            cash=state["cash"],
            nav=nav,
            positions=positions,
            run_context_id=targets[0]["run_context_id"] if targets else "wrk-empty",
        )
        return {"status": "ok", "orders": order_items, "snapshot_id": snapshot_id, "cash": state["cash"], "nav": nav}

    def _decorate_positions(
        self,
        positions: dict[str, dict[str, Any]],
        mark_prices: dict[str, float],
        quote_meta_by_symbol: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        enriched: dict[str, dict[str, Any]] = {}
        for symbol, position in positions.items():
            quantity = int(position.get("quantity", 0))
            avg_cost = float(position.get("avg_cost", 0.0))
            quote_meta = quote_meta_by_symbol.get(symbol, {})
            mark_price = float(quote_meta.get("price", mark_prices.get(symbol, avg_cost)))
            market_value = round(quantity * mark_price, 2)
            cost_basis = round(quantity * avg_cost, 2)
            unrealized_pnl = round(market_value - cost_basis, 2)
            change_pct = round((mark_price - avg_cost) / avg_cost, 6) if avg_cost else 0.0
            enriched[symbol] = {
                **position,
                "mark_price": mark_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "unrealized_pnl": unrealized_pnl,
                "change_pct": change_pct,
                "mark_time": quote_meta.get("as_of"),
                "quote_status": quote_meta.get("status", "ok"),
            }
        return enriched
```

- [ ] **Step 4: Run the execution-service test to confirm it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_execution_service.py::test_paper_execution_service_records_lifecycle_and_reconcile_snapshot -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/execution/paper_execution_service.py tests/test_paper_execution_service.py
git commit -m "feat: persist order lifecycle and reconcile snapshots"
```

### Task 4: Enrich Dashboard And Reconciliation API Contracts

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/routes_reconciliation.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write the failing dashboard API tests**

```python
# tests/test_dashboard_api.py
from datetime import datetime

from fastapi.testclient import TestClient


def test_run_endpoint_returns_traceable_target_order_and_reconcile_details(test_app, monkeypatch):
    from src.api import routes_dashboard

    class FakeSnap:
        def __init__(self, close: float):
            self.close = close
            self.timestamp = datetime(2026, 6, 14, 10, 0, 0)

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", lambda self, symbol: FakeSnap(100.0))

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )

    payload = response.json()
    target_done = next(step for step in payload["latest_run"]["steps"] if step["stage"] == "target" and step["status"] == "done")
    reconcile_done = next(step for step in payload["latest_run"]["steps"] if step["stage"] == "reconcile" and step["status"] == "done")

    assert payload["latest_run"]["run_context_id"].startswith("wrk-")
    assert {"decision_run_id", "target_position_id", "status", "price", "lot_size"}.issubset(target_done["items"][0].keys())
    assert {"execution_order_id", "filled_quantity", "status_code", "submitted_at", "filled_at"}.issubset(payload["latest_run"]["order_items"][0].keys())
    assert {"symbol", "avg_cost", "mark_price", "change_pct", "unrealized_pnl", "mark_time"}.issubset(reconcile_done["items"][0].keys())
    assert "duration_ms" in reconcile_done


def test_run_endpoint_surfaces_zero_order_breakdown_as_target_items(test_app, monkeypatch):
    from src.api import routes_dashboard

    class ExpensiveSnap:
        close = 2000.0
        timestamp = datetime(2026, 6, 14, 10, 0, 0)

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", lambda self, symbol: ExpensiveSnap())

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "watchlist": ["600519.SH"],
            "capital_base": 10_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )
    payload = response.json()
    target_done = next(step for step in payload["latest_run"]["steps"] if step["stage"] == "target" and step["status"] == "done")

    assert target_done["items"][0]["status"] == "SKIPPED"
    assert target_done["items"][0]["status_reason"] == "lot_size"
    assert target_done["items"][0]["requested_quantity"] == 1.0


def test_reconciliation_status_route_supports_run_context_filter(test_app, monkeypatch):
    from src.api import routes_dashboard

    class FakeSnap:
        close = 100.0
        timestamp = datetime(2026, 6, 14, 10, 0, 0)

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", lambda self, symbol: FakeSnap())

    client = TestClient(test_app)
    run_payload = client.post(
        "/api/v1/dashboard/run",
        json={
            "watchlist": ["600519.SH"],
            "capital_base": 1_000_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    ).json()
    run_context_id = run_payload["latest_run"]["run_context_id"]

    response = client.get(f"/api/v1/reconciliation/status?run_context_id={run_context_id}")
    payload = response.json()

    assert payload["run_context_id"] == run_context_id
    assert payload["items"][0]["symbol"] == "600519.SH"
```

- [ ] **Step 2: Run the dashboard API tests to confirm they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_returns_traceable_target_order_and_reconcile_details tests/test_dashboard_api.py::test_run_endpoint_surfaces_zero_order_breakdown_as_target_items tests/test_dashboard_api.py::test_reconciliation_status_route_supports_run_context_filter -v
```

Expected:

- Missing `duration_ms`, `mark_time`, `filled_quantity`, or `status_code`
- `target_done` still contains only a message instead of itemized target diagnostics
- `/api/v1/reconciliation/status` ignores `run_context_id`

- [ ] **Step 3: Implement the enriched dashboard payload and reconciliation route**

```python
# src/api/routes_dashboard.py
from time import perf_counter


def _measure_stage(stage_metrics: dict[str, dict], stage: str, started_at: str, started_counter: float) -> None:
    stage_metrics[stage] = {
        "started_at": started_at,
        "finished_at": _now_cst().isoformat(),
        "duration_ms": int((perf_counter() - started_counter) * 1000),
    }


def _describe_target_reason(target: dict, risk: dict | None) -> str:
    if target["action"] == "BUY" and target["quantity"] == 0:
        return (
            f"价格 {target['price']:.2f}，lot_size={target['lot_size']}，"
            f"原始数量 {target['raw_quantity']:.4f}，取整后为 0"
        )
    if risk and not risk["approved"]:
        details = risk.get("details") or {}
        if risk["rule_name"] == "cash":
            return f"可用资金 {details.get('available_cash'):.0f}，目标金额 {details.get('requested_value'):.0f}"
        if risk["rule_name"] == "max_position_ratio":
            ratio = float(details.get("next_position_ratio", 0.0))
            return f"目标仓位 {(ratio * 100):.2f}% 超过上限 {(details.get('max_position_ratio', 0.0) * 100):.2f}%"
        if risk["rule_name"] == "t_plus_one":
            return "A 股 T+1 限制，当日买入不可卖出"
        return risk["reason"]
    return "可执行"


def _build_reconcile_items(snapshot: dict | None, orders: list[dict]) -> list[dict]:
    if not snapshot:
        return []
    fee_by_symbol: dict[str, float] = {}
    order_ids_by_symbol: dict[str, list[str]] = {}
    for order in orders:
        symbol = order["symbol"]
        fee_by_symbol[symbol] = round(fee_by_symbol.get(symbol, 0.0) + float(order.get("fee", 0.0) or 0.0), 2)
        order_ids_by_symbol.setdefault(symbol, []).append(order["execution_order_id"])

    items = []
    for symbol, pos in (snapshot.get("positions") or {}).items():
        items.append(
            {
                "symbol": symbol,
                "quantity": int(pos.get("quantity", 0)),
                "avg_cost": float(pos.get("avg_cost", 0.0)),
                "mark_price": float(pos.get("mark_price", 0.0)),
                "change_pct": float(pos.get("change_pct", 0.0)),
                "unrealized_pnl": float(pos.get("unrealized_pnl", 0.0)),
                "fee_total": fee_by_symbol.get(symbol, 0.0),
                "mark_time": pos.get("mark_time"),
                "quote_status": pos.get("quote_status", "ok"),
                "execution_order_ids": order_ids_by_symbol.get(symbol, []),
            }
        )
    return sorted(items, key=lambda item: item["symbol"])


@router.post("/api/v1/dashboard/run")
def run_shadow_once(config: dict | None = None, store=Depends(get_runtime_store)) -> dict:
    ...
    stage_metrics: dict[str, dict] = {}
    decision_started_at = _now_cst().isoformat()
    decision_started_counter = perf_counter()
    quote_meta_by_symbol: dict[str, dict] = {}
    price_by_symbol: dict[str, float] = {}

    for symbol in watchlist:
        try:
            real_snap = provider.get_realtime_quote(symbol)
            if real_snap is None:
                quote_meta_by_symbol[symbol] = {"price": 100.0, "as_of": None, "status": "fallback"}
                price_by_symbol[symbol] = 100.0
            else:
                quote_meta_by_symbol[symbol] = {
                    "price": float(real_snap.close),
                    "as_of": real_snap.timestamp.isoformat() if getattr(real_snap, "timestamp", None) else None,
                    "status": "ok",
                }
                price_by_symbol[symbol] = float(real_snap.close)
        except Exception:
            quote_meta_by_symbol[symbol] = {"price": 100.0, "as_of": None, "status": "fallback"}
            price_by_symbol[symbol] = 100.0

    ...
    decision_run_id = store.insert_decision_run(
        symbol=symbol,
        prompt_hash=f"dashboard-{run_context_id}",
        run_context_id=run_context_id,
        ...
    )
    ...
    _measure_stage(stage_metrics, "decision", decision_started_at, decision_started_counter)

    target_started_at = _now_cst().isoformat()
    target_started_counter = perf_counter()
    targets = build_target_positions(...)
    executable_targets = []
    target_items = []
    for target in targets:
        decision_run_id = next(row["decision_run_id"] for row in decision_items if row["symbol"] == target["symbol"])
        risk = evaluate_risk_gate(...)
        status = "ACTIVE"
        status_reason = "ready"
        if target["action"] == "BUY" and target["quantity"] == 0:
            status = "SKIPPED"
            status_reason = "lot_size"
        elif not risk["approved"]:
            status = "BLOCKED"
            status_reason = risk["rule_name"]

        target_position_id = store.insert_target_position(
            decision_run_id=decision_run_id,
            run_context_id=run_context_id,
            symbol=target["symbol"],
            action=target["action"],
            target_value=target["target_value"],
            target_position_ratio=target["target_position_ratio"],
            expires_at=target["expires_at"],
            status=status,
            status_reason=status_reason,
            price=target["price"],
            lot_size=target["lot_size"],
            requested_quantity=target["raw_quantity"],
            notional=target["notional"],
            diagnostics={
                "raw_quantity": target["raw_quantity"],
                "rounding_loss_quantity": target["rounding_loss_quantity"],
                **(risk.get("details") or {}),
            },
        )
        if not risk["approved"]:
            store.insert_risk_gate_event(
                run_context_id=run_context_id,
                target_position_id=target_position_id,
                symbol=target["symbol"],
                approved=False,
                rule_name=risk["rule_name"],
                reason=risk["reason"],
                details=risk["details"],
            )
        target_items.append(
            {
                "decision_run_id": decision_run_id,
                "target_position_id": target_position_id,
                "run_context_id": run_context_id,
                "symbol": target["symbol"],
                "action": target["action"],
                "target_quantity": target["quantity"],
                "target_position_ratio": target["target_position_ratio"],
                "status": status,
                "status_reason": status_reason,
                "display_reason": _describe_target_reason(target, risk),
                "price": target["price"],
                "lot_size": target["lot_size"],
                "requested_quantity": target["raw_quantity"],
                "rounding_loss_quantity": target["rounding_loss_quantity"],
                "quote_as_of": quote_meta_by_symbol[target["symbol"]]["as_of"],
            }
        )
        if status == "ACTIVE":
            executable_targets.append({**target, "target_position_id": target_position_id, "run_context_id": run_context_id})
    _measure_stage(stage_metrics, "target", target_started_at, target_started_counter)

    execute_started_at = _now_cst().isoformat()
    execute_started_counter = perf_counter()
    if not decision_only and executable_targets:
        execution_result = PaperExecutionService(
            store=store,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
        ).execute_targets(
            targets=executable_targets,
            initial_state=account_state,
            mark_prices=price_by_symbol,
            quote_meta_by_symbol=quote_meta_by_symbol,
            trade_date=_now_cst().date().isoformat(),
        )
        order_items.extend(execution_result["orders"])
    _measure_stage(stage_metrics, "execute", execute_started_at, execute_started_counter)

    reconcile_started_at = _now_cst().isoformat()
    reconcile_started_counter = perf_counter()
    snapshot = store.get_latest_account_snapshot(run_context_id=run_context_id)
    reconcile_items = _build_reconcile_items(snapshot, order_items)
    _measure_stage(stage_metrics, "reconcile", reconcile_started_at, reconcile_started_counter)

    latest_run = _build_run_timeline(
        run_context_id=run_context_id,
        watchlist=watchlist,
        capital_base=capital_base,
        decision_mode=payload.get("decision_mode", "mock"),
        decision_items=decision_items,
        target_items=target_items,
        order_items=order_items,
        reconcile_items=reconcile_items,
        decision_only=decision_only,
        daily_pnl=daily_pnl,
        stage_metrics=stage_metrics,
    )
    latest_run["reconcile_items"] = reconcile_items
    ...


def _build_run_timeline(
    run_context_id: str | None,
    watchlist: list[str],
    capital_base: int,
    decision_mode: str,
    decision_items: list[dict],
    target_items: list[dict],
    order_items: list[dict],
    reconcile_items: list[dict],
    decision_only: bool,
    daily_pnl: float,
    stage_metrics: dict[str, dict],
) -> dict:
    ...
    target_done_step = {
        "stage": "target",
        "status": "done",
        "timestamp": stage_metrics["target"]["finished_at"],
        "started_at": stage_metrics["target"]["started_at"],
        "finished_at": stage_metrics["target"]["finished_at"],
        "duration_ms": stage_metrics["target"]["duration_ms"],
        "items": target_items,
    }
    ...
    if decision_only:
        ...
    elif order_items:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": stage_metrics["execute"]["finished_at"],
                    "started_at": stage_metrics["execute"]["started_at"],
                    "finished_at": stage_metrics["execute"]["finished_at"],
                    "duration_ms": stage_metrics["execute"]["duration_ms"],
                    "items": order_items,
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": stage_metrics["reconcile"]["finished_at"],
                    "started_at": stage_metrics["reconcile"]["started_at"],
                    "finished_at": stage_metrics["reconcile"]["finished_at"],
                    "duration_ms": stage_metrics["reconcile"]["duration_ms"],
                    "items": reconcile_items,
                    "message": f"所有订单已确认，持仓已更新。模拟盈亏: {_format_pnl_label(daily_pnl)}",
                },
            ]
        )
    ...
    return {
        "run_context_id": run_context_id,
        "started_at": stage_metrics["decision"]["started_at"],
        "finished_at": stage_metrics["reconcile"]["finished_at"],
        "status": "completed",
        "steps": steps,
        "order_items": order_items,
    }


def _build_workbench_payload(...):
    reconciliation = store.get_reconciliation_status()
    ...
    target_rows = store.list_target_positions(limit=page_size, offset=t_offset)
    active_target_count = store.count_active_target_positions()
    ...
    return {
        ...
        "risk": {
            "active_target_count": active_target_count,
            "open_orders": reconciliation.get("open_orders", 0),
            "broker_event_count": reconciliation.get("broker_event_count", 0),
            "healthy": reconciliation.get("healthy", False),
            "daily_pnl": daily_pnl,
        },
        "history": {
            "decisions": decisions,
            "orders": orders,
            "targets": targets,
            "reconcile": reconciliation.get("items", []),
            "events": _list_recent_events(store, limit=page_size),
        },
        ...
    }
```

```python
# src/api/routes_reconciliation.py
from fastapi import APIRouter, Depends, Query

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/reconciliation/status")
def get_reconciliation_status(
    run_context_id: str | None = Query(default=None),
    store=Depends(get_runtime_store),
) -> dict:
    return store.get_reconciliation_status(run_context_id=run_context_id)
```

- [ ] **Step 4: Run the dashboard API tests to confirm they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_returns_traceable_target_order_and_reconcile_details tests/test_dashboard_api.py::test_run_endpoint_surfaces_zero_order_breakdown_as_target_items tests/test_dashboard_api.py::test_reconciliation_status_route_supports_run_context_filter -v
```

Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py src/api/routes_reconciliation.py src/storage/runtime_store.py tests/test_dashboard_api.py
git commit -m "feat: expose dashboard trade trace and reconcile details"
```

### Task 5: Render The New Trace Data In Dashboard UI

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Test: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write the failing page-contract test**

```python
# tests/test_dashboard_page_contract.py
def test_render_dashboard_html_contains_reconcile_and_trace_markers():
    html = render_dashboard_html()
    for marker in [
        'id="tab-reconcile"',
        'id="tb-reconcile"',
        'id="run-trace-id"',
        'id="tb-targets"',
        'id="tb-orders"',
    ]:
        assert marker in html
```

- [ ] **Step 2: Run the page-contract test to confirm it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_reconcile_and_trace_markers -v
```

Expected: FAIL because the new reconciliation tab and run trace marker do not exist yet.

- [ ] **Step 3: Add the reconciliation tab, lifecycle columns, and timeline rendering**

```html
<!-- src/api/dashboard_page/partials/view_dashboard.html -->
<div id="mode-status" class="mode-status-box"></div>
<div id="run-trace-id" class="trace-inline">--</div>

...

<div class="tab-bar">
  <button class="active" onclick="switchTab(this,'tab-decisions')">决策</button>
  <button onclick="switchTab(this,'tab-orders')">订单</button>
  <button onclick="switchTab(this,'tab-targets')">目标仓位</button>
  <button onclick="switchTab(this,'tab-reconcile')">对账</button>
  <button onclick="switchTab(this,'tab-errors')">异常</button>
</div>

...

<div class="tab-pane" id="tab-orders">
  <table>
    <thead>
      <tr>
        <th>时间</th><th>股票</th><th>方向</th><th>下单/成交</th><th>限价/成交价</th>
        <th>手续费</th><th>状态码</th><th>原因</th><th>链路</th>
      </tr>
    </thead>
    <tbody id="tb-orders"><tr><td colspan="9" style="color:var(--dim)">暂无数据</td></tr></tbody>
  </table>
  <div id="pag-orders" class="pagination"></div>
</div>

<div class="tab-pane" id="tab-targets">
  <table>
    <thead>
      <tr><th>股票</th><th>目标数量</th><th>目标权重</th><th>状态</th><th>原因</th><th>链路</th></tr>
    </thead>
    <tbody id="tb-targets"><tr><td colspan="6" style="color:var(--dim)">暂无数据</td></tr></tbody>
  </table>
  <div id="pag-targets" class="pagination"></div>
</div>

<div class="tab-pane" id="tab-reconcile">
  <table>
    <thead>
      <tr>
        <th>股票</th><th>数量</th><th>成本价</th><th>现价</th><th>涨跌幅</th>
        <th>未实现盈亏</th><th>手续费</th><th>行情时间</th>
      </tr>
    </thead>
    <tbody id="tb-reconcile"><tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr></tbody>
  </table>
</div>
```

```javascript
// src/api/dashboard_page/scripts/dashboard.js
function renderOrders(list) {
  const rows = toList(list);
  ...
  tb.innerHTML = page.map(item => {
    const time = formatTime(pickFirst(item, ['filled_at', 'last_event_at', 'created_at']));
    const symbol = normalizeText(item.symbol);
    const side = normalizeText(item.action).toUpperCase();
    const lifecycle = `${normalizeText(item.quantity)}/${normalizeText(item.filled_quantity)}`;
    const price = `${formatCurrency(item.limit_price)} / ${formatCurrency(item.fill_price)}`;
    const fee = formatCurrency(item.fee);
    const statusCode = normalizeText(item.status_code, '--').toUpperCase();
    const reason = normalizeText(pickFirst(item, ['display_reason', 'status_reason'], '--'));
    const trace = normalizeText(item.execution_order_id, '--');
    return `<tr><td>${escapeHtml(time)}</td><td>${escapeHtml(symbol)}</td><td>${escapeHtml(side)}</td><td>${escapeHtml(lifecycle)}</td><td>${escapeHtml(price)}</td><td>${escapeHtml(fee)}</td><td>${escapeHtml(statusCode)}</td><td title="${escapeHtml(reason)}">${escapeHtml(reason)}</td><td class="trace-cell">${escapeHtml(trace)}</td></tr>`;
  }).join('');
}


function renderTargets(list) {
  const rows = toList(list);
  ...
  tb.innerHTML = page.map(item => {
    const symbol = normalizeText(item.symbol);
    const quantity = normalizeText(item.target_quantity);
    const weight = formatPercent(item.target_position_ratio);
    const status = normalizeText(item.status, '--').toUpperCase();
    const reason = normalizeText(pickFirst(item, ['display_reason', 'status_reason'], '--'));
    const trace = normalizeText(item.target_position_id, '--');
    return `<tr><td>${escapeHtml(symbol)}</td><td>${escapeHtml(quantity)}</td><td>${escapeHtml(weight)}</td><td>${escapeHtml(status)}</td><td title="${escapeHtml(reason)}">${escapeHtml(reason)}</td><td class="trace-cell">${escapeHtml(trace)}</td></tr>`;
  }).join('');
}


function renderReconcile(list) {
  const rows = toList(list);
  const tb = document.getElementById('tb-reconcile');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  tb.innerHTML = rows.map(item => {
    const symbol = normalizeText(item.symbol);
    const qty = normalizeText(item.quantity);
    const avgCost = formatCurrency(item.avg_cost);
    const markPrice = formatCurrency(item.mark_price);
    const change = formatPercent(item.change_pct);
    const pnl = formatCurrency(item.unrealized_pnl);
    const fee = formatCurrency(item.fee_total);
    const markTime = formatTime(item.mark_time);
    const pnlClass = Number(item.unrealized_pnl) > 0 ? 'green' : Number(item.unrealized_pnl) < 0 ? 'red' : '';
    return `<tr><td>${escapeHtml(symbol)}</td><td>${escapeHtml(qty)}</td><td>${escapeHtml(avgCost)}</td><td>${escapeHtml(markPrice)}</td><td>${escapeHtml(change)}</td><td class="${pnlClass}">${escapeHtml(pnl)}</td><td>${escapeHtml(fee)}</td><td>${escapeHtml(markTime)}</td></tr>`;
  }).join('');
}


function stageBodyHtml(step) {
  const items = toList(step.items);
  if (items.length) {
    const first = items[0] || {};
    if (first.mark_price !== undefined || first.unrealized_pnl !== undefined) {
      const rows = items.map(item => {
        return `<tr><td>${escapeHtml(normalizeText(item.symbol))}</td><td>${escapeHtml(formatCurrency(item.avg_cost))}</td><td>${escapeHtml(formatCurrency(item.mark_price))}</td><td>${escapeHtml(formatPercent(item.change_pct))}</td><td>${escapeHtml(formatCurrency(item.unrealized_pnl))}</td><td>${escapeHtml(formatTime(item.mark_time))}</td></tr>`;
      }).join('');
      return `<table><tr><th>股票</th><th>成本价</th><th>现价</th><th>涨跌幅</th><th>未实现盈亏</th><th>行情时间</th></tr>${rows}</table>`;
    }
    if (first.status_reason !== undefined || first.filled_quantity !== undefined) {
      const rows = items.map(item => {
        const symbol = escapeHtml(normalizeText(item.symbol));
        const action = escapeHtml(normalizeText(item.action, '--').toUpperCase());
        const qty = escapeHtml(normalizeText(item.quantity, '--'));
        const filled = escapeHtml(normalizeText(item.filled_quantity ?? item.target_quantity, '--'));
        const status = escapeHtml(normalizeText(item.status_code || item.status, '--').toUpperCase());
        const reason = escapeHtml(normalizeText(pickFirst(item, ['display_reason', 'status_reason'], '--')));
        return `<tr><td>${symbol}</td><td>${action}</td><td>${qty}</td><td>${filled}</td><td>${status}</td><td>${reason}</td></tr>`;
      }).join('');
      return `<table><tr><th>股票</th><th>方向</th><th>数量</th><th>已成交</th><th>状态</th><th>原因</th></tr>${rows}</table>`;
    }
  }
  return escapeHtml(normalizeText(step.message || '--'));
}


function renderTimeline(latestRun) {
  ...
  document.getElementById('run-trace-id').textContent = latestRun?.run_context_id || '--';
  steps.forEach(step => {
    const time = formatTime(pickFirst(step, ['finished_at', 'timestamp', 'time']));
    const duration = step.duration_ms != null ? ` · ${step.duration_ms}ms` : '';
    ...
    div.innerHTML = `
      <div class="step-head">
        <span class="step-tag ${stage}">${escapeHtml(stageLabel(stage))}</span>
        <span class="step-time">${escapeHtml(`${time}${duration}`)}</span>
      </div>
      <div class="step-body">${stageBodyHtml(stepCopy)}</div>
    `;
  });
}


function renderWorkbench(data, killStatus) {
  ...
  renderTargets(data.history?.targets || []);
  renderOrders(data.history?.orders || []);
  renderReconcile(data.history?.reconcile || data.latest_run?.reconcile_items || []);
  renderTimeline(data.latest_run || { steps: [] });
}
```

```css
/* src/api/dashboard_page/styles/dashboard.css */
.trace-inline {
  margin-top: 8px;
  color: var(--dim);
  font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-all;
}

.trace-cell {
  color: var(--dim);
  font: 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap;
}

#tab-orders table,
#tab-targets table,
#tab-reconcile table {
  width: 100%;
  table-layout: fixed;
}

#tab-orders td,
#tab-targets td,
#tab-reconcile td {
  vertical-align: top;
}
```

- [ ] **Step 4: Run the page-contract test to confirm it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_reconcile_and_trace_markers -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard_page/partials/view_dashboard.html src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/styles/dashboard.css tests/test_dashboard_page_contract.py
git commit -m "feat: render dashboard trade trace and reconcile tab"
```

### Task 6: Update SOP And Run Focused Regression Verification

**Files:**
- Modify: `docs/sop.md`
- Test: `tests/test_target_planner.py`
- Test: `tests/test_risk_gate.py`
- Test: `tests/test_runtime_store_pg.py`
- Test: `tests/test_paper_execution_service.py`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Update the SOP wording so beginners can read the new output**

```markdown
<!-- docs/sop.md -->
## 运行完成后重点看 4 个区块

1. `目标仓位`
   - `状态=ACTIVE`：这只股票进入了可执行目标。
   - `状态=SKIPPED`：通常是资金太少或最小交易单位限制，重点看 `原因` 里的 `lot_size / 原始数量 / 取整后数量`。
   - `状态=BLOCKED`：被风控拦截，重点看 `原因` 里的 `可用资金 / 仓位上限 / T+1`。

2. `订单`
   - `下单/成交`：前一个数字是计划数量，后一个数字是已成交数量。
   - `状态码`：`SUBMITTED / PARTIALLY_FILLED / FILLED / REJECTED`。
   - `原因`：说明为什么部分成交、未成交或被拒绝。

3. `对账`
   - `成本价`：你的持仓平均成本。
   - `现价`：本轮对账使用的行情价格。
   - `涨跌幅`：这里是相对持仓成本的浮动比例。
   - `未实现盈亏`：如果现在卖出，大致浮盈浮亏是多少。
   - `行情时间`：这次对账用的是哪一刻的价格；如果为空，说明本轮用了回退价格。

4. `最近运行记录`
   - 每一步现在都有 `耗时`。
   - 顶部的 `run_context_id` 可以用来和日志、API、数据库记录对上同一轮运行。
```

- [ ] **Step 2: Run the focused regression suite**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_target_planner.py \
  tests/test_risk_gate.py \
  tests/test_runtime_store_pg.py \
  tests/test_paper_execution_service.py \
  tests/test_dashboard_api.py \
  tests/test_dashboard_page_contract.py -q
```

Expected: all listed tests pass.

- [ ] **Step 3: Run the migration on the real runtime schema**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

Expected: database schema reaches revision `20260614_000010`.

- [ ] **Step 4: Do a minimal manual API verification**

Run:

```bash
curl -s -X POST http://localhost:8000/api/v1/dashboard/run \
  -H 'Content-Type: application/json' \
  -d '{"watchlist":["600519.SH"],"capital_base":1000000,"max_position_ratio":0.2,"execution_mode":"full"}'
```

Expected:

- `latest_run.run_context_id` is non-empty
- `latest_run.steps` contains `duration_ms`
- `latest_run.order_items[0]` contains `filled_quantity`, `status_code`, `submitted_at`, `filled_at`
- `latest_run.reconcile_items[0]` contains `avg_cost`, `mark_price`, `change_pct`, `unrealized_pnl`, `mark_time`

- [ ] **Step 5: Do a minimal manual UI verification**

Open:

```text
http://localhost:8000/dashboard
```

Expected:

- `目标仓位` tab shows `状态` and `原因`
- `订单` tab shows lifecycle columns
- `对账` tab shows per-stock `成本价 / 现价 / 涨跌幅 / 未实现盈亏 / 行情时间`
- `最近运行记录` shows a `run_context_id` and per-stage `xxms`

- [ ] **Step 6: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add docs/sop.md
git commit -m "docs: explain dashboard trade trace outputs"
```

## Self-Review

**Spec coverage**

- Issue 1 `对账缺少单票明细`: Task 3 and Task 4 persist and expose `avg_cost / mark_price / change_pct / unrealized_pnl / fee_total / mark_time`; Task 5 renders them.
- Issue 2 `目标仓位缺少没下成的拆解`: Task 2 keeps zero-quantity target attempts and risk details; Task 4 maps them to target rows; Task 5 renders them.
- Issue 3 `执行层缺少订单生命周期`: Task 1 adds lifecycle fields; Task 3 persists them; Task 4 exposes them; Task 5 renders them.
- Issue 4 `缺少链路追踪`: Task 1 adds `run_context_id` and IDs on rows; Task 4 returns them; Task 5 shows them.
- Issue 5 `缺少风控拦截可解释原因`: Task 2 returns structured risk details; Task 4 translates them into display text and status codes.
- Issue 6 `缺少行情时点和耗时`: Task 3 persists `mark_time`; Task 4 adds `duration_ms`; Task 5 renders both.

**Placeholder scan**

- No `TODO`, `TBD`, “implement later”, or “write tests for the above” placeholders remain.
- Every code-changing step includes concrete code or concrete command output expectations.

**Type consistency**

- Canonical trace key: `run_context_id`
- Canonical target reason fields: `status_reason`, `display_reason`, `diagnostics`
- Canonical order lifecycle fields: `filled_quantity`, `fill_price`, `fee`, `pnl_delta`, `status_code`, `status_reason`, `submitted_at`, `filled_at`, `last_event_at`
- Canonical reconciliation fields: `avg_cost`, `mark_price`, `change_pct`, `unrealized_pnl`, `fee_total`, `mark_time`, `quote_status`
- Canonical timing fields: `started_at`, `finished_at`, `duration_ms`
