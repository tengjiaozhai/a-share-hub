# Dashboard Trade Run Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one authoritative backend path for dashboard trade runs that returns stock-level reconciliation, unified run PnL, and step-by-step stream events.

**Architecture:** Move the shadow-run orchestration out of `routes_dashboard.py` into a dedicated backend service, persist per-run summaries plus ordered run events in PostgreSQL, and make the dashboard consume that single source of truth. Replace the blocking `POST /api/v1/dashboard/run` flow with `POST /api/v1/dashboard/runs` plus `GET /api/v1/dashboard/runs/{run_context_id}/events`, and keep `GET /api/v1/dashboard/workbench` as the final snapshot reader.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Python services, pytest

---

## Scope Check

This plan is backend-only. It covers schema, runtime-store APIs, run orchestration, reconciliation payloads, and SSE endpoints. It does not include HTML, CSS, or browser-side rendering work.

## File Structure

- Create: `alembic/versions/20260615_000011_dashboard_run_summary_and_events.py`
  Add the canonical run-summary table and run-event log table.
- Create: `src/execution/shadow_run_service.py`
  Own the end-to-end shadow-trading pipeline, event emission, and final snapshot assembly.
- Create: `tests/test_dashboard_stream_api.py`
  Lock the new `POST /runs` and `GET /runs/{id}/events` behavior.
- Modify: `src/storage/models.py`
  Define `DashboardRunSummaryRow` and `DashboardRunEventRow`.
- Modify: `src/storage/runtime_store.py`
  Persist and query run summaries, ordered stream events, authoritative target quantities, and filtered workbench snapshots.
- Modify: `src/execution/paper_execution_service.py`
  Write enriched account-snapshot position data that reconciliation can display directly.
- Modify: `src/api/routes_dashboard.py`
  Replace the blocking run endpoint with run-start and stream endpoints; read final run snapshots from `RuntimeStore`.
- Modify: `src/api/routes_reconciliation.py`
  Accept `run_context_id` and return stock-level reconciliation items from the same backend source as the dashboard.
- Modify: `tests/test_runtime_store_pg.py`
  Cover run-summary persistence and ordered run-event replay.
- Modify: `tests/test_dashboard_api.py`
  Cover workbench filtering, authoritative target quantity, reconcile items, and unified run PnL.
- Modify: `tests/test_paper_execution_service.py`
  Cover enriched reconciliation snapshot fields.

### Task 1: Persist Dashboard Run Summary And Ordered Event Log

**Files:**
- Create: `alembic/versions/20260615_000011_dashboard_run_summary_and_events.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_runtime_store_pg.py`

- [ ] **Step 1: Write the failing storage test**

```python
# tests/test_runtime_store_pg.py
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_dashboard_run_summary_and_event_log(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.upsert_dashboard_run_summary(
        run_context_id="wrk-001",
        trade_date="2026-06-15",
        decision_mode="real",
        execution_mode="full",
        capital_base=10_000,
        status="running",
        execution_fee_total=0.12,
        realized_pnl=0.0,
        unrealized_pnl=-0.48,
        net_pnl=-0.60,
        started_at="2026-06-15T20:15:06+08:00",
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": "wrk-001"}},
    )
    first_seq = store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "请求已受理"},
    )
    second_seq = store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="stage.updated",
        stage="decision",
        status="done",
        payload={"items": [{"symbol": "NVDA", "action": "BUY"}]},
    )

    summary = store.get_dashboard_run_summary("wrk-001")
    events = store.list_dashboard_run_events("wrk-001")

    assert summary["execution_fee_total"] == 0.12
    assert summary["net_pnl"] == -0.60
    assert summary["latest_workbench"]["latest_run"]["run_context_id"] == "wrk-001"
    assert [event["seq"] for event in events] == [first_seq, second_seq]
    assert events[1]["payload"]["items"][0]["symbol"] == "NVDA"
```

- [ ] **Step 2: Run the storage test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py::test_runtime_store_persists_dashboard_run_summary_and_event_log -v
```

Expected: FAIL with `AttributeError` because `upsert_dashboard_run_summary`, `append_dashboard_run_event`, or `get_dashboard_run_summary` do not exist.

- [ ] **Step 3: Implement the migration, models, and runtime-store APIs**

```python
# alembic/versions/20260615_000011_dashboard_run_summary_and_events.py
from alembic import op
import sqlalchemy as sa


revision = "20260615_000011"
down_revision = "20260614_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_run_summaries",
        sa.Column("run_context_id", sa.String(length=64), primary_key=True),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("decision_mode", sa.String(length=16), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("capital_base", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("execution_fee_total", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("net_pnl", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("latest_workbench_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "dashboard_run_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("run_context_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_dashboard_run_events_run_context_seq", "dashboard_run_events", ["run_context_id", "seq"], unique=True)
```

```python
# src/storage/models.py
class DashboardRunSummaryRow(Base):
    __tablename__ = "dashboard_run_summaries"

    run_context_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)
    decision_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    capital_base: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_fee_total: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    net_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_workbench_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class DashboardRunEventRow(Base):
    __tablename__ = "dashboard_run_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/storage/runtime_store.py
def upsert_dashboard_run_summary(
    self,
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
        "trade_date": trade_date,
        "decision_mode": decision_mode,
        "execution_mode": execution_mode,
        "capital_base": capital_base,
        "status": status,
        "execution_fee_total": execution_fee_total,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "net_pnl": net_pnl,
        "started_at": datetime.fromisoformat(started_at),
        "finished_at": datetime.fromisoformat(finished_at) if finished_at else None,
        "latest_workbench_json": json.dumps(latest_workbench, ensure_ascii=True, sort_keys=True),
        "updated_at": datetime.utcnow(),
    }
    with self.engine.begin() as conn:
        existing = conn.execute(
            select(DashboardRunSummaryRow).where(DashboardRunSummaryRow.run_context_id == run_context_id)
        ).fetchone()
        if existing is None:
            conn.execute(DashboardRunSummaryRow.__table__.insert().values(created_at=datetime.utcnow(), **values))
        else:
            conn.execute(
                DashboardRunSummaryRow.__table__.update()
                .where(DashboardRunSummaryRow.run_context_id == run_context_id)
                .values(**values)
            )


def get_dashboard_run_summary(self, run_context_id: str) -> dict | None:
    with self.engine.begin() as conn:
        row = conn.execute(
            select(DashboardRunSummaryRow).where(DashboardRunSummaryRow.run_context_id == run_context_id)
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


def append_dashboard_run_event(
    self,
    run_context_id: str,
    event_type: str,
    stage: str,
    status: str,
    payload: dict,
) -> int:
    event_id = f"dre-{uuid.uuid4().hex[:12]}"
    with self.engine.begin() as conn:
        current_seq = conn.execute(
            select(func.max(DashboardRunEventRow.seq)).where(DashboardRunEventRow.run_context_id == run_context_id)
        ).scalar_one()
        next_seq = int(current_seq or 0) + 1
        conn.execute(
            DashboardRunEventRow.__table__.insert().values(
                event_id=event_id,
                run_context_id=run_context_id,
                seq=next_seq,
                event_type=event_type,
                stage=stage,
                status=status,
                payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
            )
        )
    return next_seq


def list_dashboard_run_events(self, run_context_id: str, after_seq: int = 0) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(DashboardRunEventRow)
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
```

- [ ] **Step 4: Run the focused tests and migration**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py::test_runtime_store_persists_dashboard_run_summary_and_event_log -v
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

Expected:

- pytest PASS
- Alembic output contains `Running upgrade 20260614_000010 -> 20260615_000011`

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add alembic/versions/20260615_000011_dashboard_run_summary_and_events.py src/storage/models.py src/storage/runtime_store.py tests/test_runtime_store_pg.py
git commit -m "feat: persist dashboard run summaries and events"
```

### Task 2: Extract Shadow Run Service And Return Authoritative Reconcile Snapshot

**Files:**
- Create: `src/execution/shadow_run_service.py`
- Modify: `src/execution/paper_execution_service.py`
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/routes_reconciliation.py`
- Modify: `tests/test_dashboard_api.py`
- Modify: `tests/test_paper_execution_service.py`

- [ ] **Step 1: Write the failing API and execution tests**

```python
# tests/test_paper_execution_service.py
from sqlalchemy import create_engine

from src.execution.paper_execution_service import PaperExecutionService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_paper_execution_service_records_reconcile_snapshot_fields(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    service.execute_targets(
        targets=[
            {
                "run_context_id": "wrk-001",
                "target_position_id": "tp-001",
                "symbol": "NVDA",
                "action": "BUY",
                "quantity": 4,
                "price": 100.0,
                "notional": 400,
            }
        ],
        initial_state={"cash": 10_000.0, "positions": {}},
        mark_prices={"NVDA": 99.90},
        quote_meta_by_symbol={"NVDA": {"as_of": "2026-06-15T20:15:06+08:00", "status": "ok"}},
        trade_date="2026-06-15",
    )

    snapshot = store.get_latest_account_snapshot(run_context_id="wrk-001")
    position = snapshot["positions"]["NVDA"]

    assert position["mark_price"] == 99.90
    assert position["market_value"] == 399.6
    assert position["unrealized_pnl"] < 0
    assert position["mark_time"] == "2026-06-15T20:15:06+08:00"
```

```python
# tests/test_dashboard_api.py
from fastapi.testclient import TestClient


def test_workbench_uses_authoritative_target_quantity_and_reconcile_items(test_app, pg_store):
    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-001",
        trade_date="2026-06-15",
        decision_mode="real",
        execution_mode="full",
        capital_base=10_000,
        status="completed",
        execution_fee_total=0.36,
        realized_pnl=0.0,
        unrealized_pnl=-0.60,
        net_pnl=-0.96,
        started_at="2026-06-15T20:15:06+08:00",
        finished_at="2026-06-15T20:15:38+08:00",
        latest_workbench={
            "latest_run": {
                "run_context_id": "wrk-001",
                "target_items": [{"symbol": "NVDA", "target_quantity": 4}],
                "reconcile_items": [{"symbol": "NVDA", "mark_price": 99.90}],
                "run_pnl_summary": {"net_pnl": -0.96},
            }
        },
    )

    client = TestClient(test_app)
    response = client.get("/api/v1/dashboard/workbench?run_context_id=wrk-001")
    payload = response.json()

    assert response.status_code == 200
    assert payload["latest_run"]["target_items"][0]["target_quantity"] == 4
    assert payload["latest_run"]["reconcile_items"][0]["mark_price"] == 99.90
    assert payload["latest_run"]["run_pnl_summary"]["net_pnl"] == -0.96
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_execution_service.py::test_paper_execution_service_records_reconcile_snapshot_fields tests/test_dashboard_api.py::test_workbench_uses_authoritative_target_quantity_and_reconcile_items -v
```

Expected: FAIL because `quote_meta_by_symbol`, `run_context_id` filtering, and `run_pnl_summary` support are missing.

- [ ] **Step 3: Implement the backend service and authoritative workbench snapshot**

```python
# src/execution/shadow_run_service.py
from __future__ import annotations

from time import perf_counter

from src.execution.paper_execution_service import PaperExecutionService
from src.portfolio.target_planner import build_target_positions
from src.risk.pre_trade_risk import evaluate_risk_gate


class ShadowRunService:
    def __init__(self, store, settings, llm, provider) -> None:
        self.store = store
        self.settings = settings
        self.llm = llm
        self.provider = provider

    def build_run_pnl_summary(self, previous_nav: float, current_nav: float, orders: list[dict], reconcile_items: list[dict]) -> dict:
        execution_fee_total = round(sum(float(order.get("fee", 0.0) or 0.0) for order in orders), 2)
        realized_pnl = round(sum(float(order.get("pnl_delta", 0.0) or 0.0) for order in orders), 2)
        unrealized_pnl = round(sum(float(item.get("unrealized_pnl", 0.0) or 0.0) for item in reconcile_items), 2)
        net_pnl = round(current_nav - previous_nav, 2)
        return {
            "execution_fee_total": execution_fee_total,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
        }

    def build_reconcile_items(self, snapshot: dict | None, orders: list[dict]) -> list[dict]:
        if snapshot is None:
            return []
        fee_by_symbol: dict[str, float] = {}
        for order in orders:
            symbol = order["symbol"]
            fee_by_symbol[symbol] = round(fee_by_symbol.get(symbol, 0.0) + float(order.get("fee", 0.0) or 0.0), 2)
        items = []
        for symbol, position in (snapshot.get("positions") or {}).items():
            items.append(
                {
                    "symbol": symbol,
                    "quantity": int(position.get("quantity", 0)),
                    "avg_cost": float(position.get("avg_cost", 0.0)),
                    "mark_price": float(position.get("mark_price", 0.0)),
                    "market_value": float(position.get("market_value", 0.0)),
                    "change_pct": float(position.get("change_pct", 0.0)),
                    "unrealized_pnl": float(position.get("unrealized_pnl", 0.0)),
                    "fee_total": fee_by_symbol.get(symbol, 0.0),
                    "mark_time": position.get("mark_time"),
                    "quote_status": position.get("quote_status", "ok"),
                }
            )
        return sorted(items, key=lambda item: item["symbol"])
```

```python
# src/execution/paper_execution_service.py
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
        mark_price = float(mark_prices.get(symbol, avg_cost))
        market_value = round(quantity * mark_price, 2)
        cost_basis = round(quantity * avg_cost, 2)
        unrealized_pnl = round(market_value - cost_basis, 2)
        change_pct = round((mark_price - avg_cost) / avg_cost, 6) if avg_cost else 0.0
        quote_meta = quote_meta_by_symbol.get(symbol, {})
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

```python
# src/api/routes_dashboard.py
@router.get("/api/v1/dashboard/workbench")
def get_workbench(
    market: str = Query(default="a"),
    account_kind: str = Query(default="auto"),
    run_context_id: str | None = Query(default=None),
    decisions_page: int = Query(default=1, ge=1),
    orders_page: int = Query(default=1, ge=1),
    targets_page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store: RuntimeStore = Depends(get_runtime_store),
) -> dict:
    if run_context_id:
        summary = store.get_dashboard_run_summary(run_context_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="run_context_id not found")
        return summary["latest_workbench"]
    payload = _build_workbench_payload(
        store,
        market=market,
        decisions_page=decisions_page,
        orders_page=orders_page,
        targets_page=targets_page,
        page_size=page_size,
    )
    payload["alpha"] = _build_alpha_panel_payload(store)
    return payload
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

- [ ] **Step 4: Run the focused tests**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_execution_service.py::test_paper_execution_service_records_reconcile_snapshot_fields tests/test_dashboard_api.py::test_workbench_uses_authoritative_target_quantity_and_reconcile_items -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/execution/shadow_run_service.py src/execution/paper_execution_service.py src/api/routes_dashboard.py src/api/routes_reconciliation.py tests/test_dashboard_api.py tests/test_paper_execution_service.py
git commit -m "feat: add authoritative reconcile snapshot for dashboard runs"
```

### Task 3: Replace Blocking Run Endpoint With Start-Run And SSE Events

**Files:**
- Create: `tests/test_dashboard_stream_api.py`
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/execution/shadow_run_service.py`
- Modify: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write the failing stream-endpoint tests**

```python
# tests/test_dashboard_stream_api.py
from fastapi.testclient import TestClient


def test_start_run_returns_accepted_and_run_context_id(test_app, monkeypatch):
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config: None)

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/runs",
        json={
            "watchlist": ["NVDA", "AAPL"],
            "capital_base": 10_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "real",
        },
    )

    payload = response.json()
    assert response.status_code == 202
    assert payload["run_context_id"].startswith("wrk-")
    assert payload["stream_url"] == f"/api/v1/dashboard/runs/{payload['run_context_id']}/events"


def test_run_events_route_streams_ordered_event_log(test_app, pg_store):
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "accepted"},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.completed",
        stage="reconcile",
        status="done",
        payload={"message": "completed"},
    )
    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-001",
        trade_date="2026-06-15",
        decision_mode="real",
        execution_mode="full",
        capital_base=10_000,
        status="completed",
        execution_fee_total=0.36,
        realized_pnl=0.0,
        unrealized_pnl=-0.60,
        net_pnl=-0.96,
        started_at="2026-06-15T20:15:06+08:00",
        finished_at="2026-06-15T20:15:38+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-001"}},
    )

    client = TestClient(test_app)
    with client.stream("GET", "/api/v1/dashboard/runs/wrk-001/events") as response:
        body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert 'event: run.accepted' in body
    assert 'event: run.completed' in body
    assert '"run_context_id": "wrk-001"' in body
```

- [ ] **Step 2: Run the stream-endpoint tests to verify they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_api.py -v
```

Expected: FAIL with `404` because `/api/v1/dashboard/runs` and `/events` do not exist.

- [ ] **Step 3: Implement run-start and SSE routes**

```python
# src/api/routes_dashboard.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse


def _launch_dashboard_run(run_context_id: str, config: dict) -> None:
    store = get_runtime_store()
    settings = Settings()
    llm = _get_llm()
    provider = AkshareProvider()
    service = ShadowRunService(store=store, settings=settings, llm=llm, provider=provider)
    service.run(run_context_id=run_context_id, config=config)


@router.post("/api/v1/dashboard/runs")
def start_dashboard_run(
    config: dict | None = None,
    background_tasks: BackgroundTasks = None,
    store: RuntimeStore = Depends(get_runtime_store),
) -> dict:
    payload = config or {}
    run_context_id = f"wrk-{_now_cst().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    store.upsert_dashboard_run_summary(
        run_context_id=run_context_id,
        trade_date=_now_cst().date().isoformat(),
        decision_mode=str(payload.get("decision_mode", "mock")),
        execution_mode="decision" if payload.get("execution_mode") == "decision" else "full",
        capital_base=int(payload.get("capital_base", 1_000_000)),
        status="accepted",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at=_now_cst().isoformat(),
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": run_context_id, "steps": []}},
    )
    store.append_dashboard_run_event(
        run_context_id=run_context_id,
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "请求已提交，等待后台执行"},
    )
    background_tasks.add_task(_launch_dashboard_run, run_context_id, payload)
    return {
        "run_context_id": run_context_id,
        "stream_url": f"/api/v1/dashboard/runs/{run_context_id}/events",
        "status": "accepted",
    }


@router.get("/api/v1/dashboard/runs/{run_context_id}/events")
def stream_dashboard_run_events(
    run_context_id: str,
    store: RuntimeStore = Depends(get_runtime_store),
) -> StreamingResponse:
    def event_iter():
        last_seq = 0
        while True:
            events = store.list_dashboard_run_events(run_context_id, after_seq=last_seq)
            for event in events:
                last_seq = event["seq"]
                yield f"event: {event['event_type']}\n"
                yield f"data: {json.dumps(event, ensure_ascii=True)}\n\n"
            summary = store.get_dashboard_run_summary(run_context_id)
            if summary and summary["status"] in {"completed", "failed"}:
                break
            time.sleep(0.2)

    return StreamingResponse(event_iter(), media_type="text/event-stream")
```

```python
# src/execution/shadow_run_service.py
def emit(self, run_context_id: str, event_type: str, stage: str, status: str, payload: dict) -> None:
    self.store.append_dashboard_run_event(
        run_context_id=run_context_id,
        event_type=event_type,
        stage=stage,
        status=status,
        payload=payload,
    )
```

- [ ] **Step 4: Run the stream-endpoint tests**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py src/execution/shadow_run_service.py tests/test_dashboard_stream_api.py tests/test_dashboard_api.py
git commit -m "feat: add dashboard run start and event stream endpoints"
```

## Self-Review

**Spec coverage**

- 对账无结果明细: Task 2 adds authoritative `reconcile_items`.
- 盈亏只有手续费、口径不统一: Task 1 and Task 2 add `dashboard_run_summaries` plus one `run_pnl_summary`.
- 多轮结果为什么不流式: Task 3 replaces the blocking run path with run-start and SSE event replay.
- 目标仓位历史回放不准: Task 2 reads authoritative `latest_workbench` instead of recomputing quantity from `target_value`.

**Placeholder scan**

- No placeholder markers remain.
- Every code-changing step includes concrete test code, concrete implementation code, and concrete commands.

**Type consistency**

- Canonical run identifier: `run_context_id`
- Canonical final aggregate: `run_pnl_summary`
- Canonical stream route: `/api/v1/dashboard/runs/{run_context_id}/events`
- Canonical start route: `/api/v1/dashboard/runs`
- Canonical reconcile payload key: `reconcile_items`
