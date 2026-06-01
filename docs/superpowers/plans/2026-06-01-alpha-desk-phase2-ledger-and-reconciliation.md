# Alpha Desk Phase 2 Ledger And Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 的 alpha 建议单和人工回填基础上，建立权威账本、基础 PnL、外部快照对账和异常视图。

**Architecture:** 新增 `src/alpha/ledger.py` 和 `src/alpha/reconciliation.py` 作为纯业务层，避免把账本逻辑埋进路由或 runtime store。运行时存储新增 alpha 持仓、组合快照、外部快照和对账结果表；dashboard 通过 workbench 汇总 alpha 组合状态、PnL 和异常。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest

---

## 前置条件

- `docs/superpowers/plans/2026-06-01-alpha-desk-phase1-foundation-and-manual-ticket.md` 已完成并合入。
- `src/alpha/`、`src/api/routes_alpha.py`、alpha ticket/fill API 和 alpha workbench 面板已经存在。

---

## 文件结构

```
a-share-hub/
├── src/
│   ├── alpha/
│   │   ├── ledger.py
│   │   ├── portfolio_service.py
│   │   └── reconciliation.py
│   ├── api/
│   │   ├── routes_alpha.py
│   │   ├── routes_dashboard.py
│   │   └── dashboard.html
│   └── storage/
│       ├── models.py
│       └── runtime_store.py
└── tests/
    ├── test_alpha_ledger.py
    ├── test_alpha_portfolio_service.py
    ├── test_alpha_reconciliation.py
    ├── test_alpha_routes.py
    ├── test_alpha_runtime_store.py
    ├── test_dashboard_alpha_tab.py
    └── test_dashboard_api.py
```

---

### Task 1: 建立 alpha 账本纯函数

**Files:**
- Create: `src/alpha/ledger.py`
- Test: `tests/test_alpha_ledger.py`

- [ ] **Step 1: 写失败测试，锁定买卖成交后的现金、持仓和 realized PnL 合同**

```python
from src.alpha.ledger import AlphaPortfolioState, AlphaPositionState, apply_manual_fill, mark_to_market


def test_apply_manual_fill_updates_cash_positions_and_realized_pnl():
    state = AlphaPortfolioState(
        cash_balance=10_000.0,
        realized_pnl=0.0,
        positions={"AAPLx": AlphaPositionState(symbol="AAPLx", quantity=1.0, avg_cost=200.0)},
    )

    next_state = apply_manual_fill(state, symbol="AAPLx", side="SELL", quantity=0.4, price=220.0)
    summary = mark_to_market(next_state, {"AAPLx": 225.0})

    assert round(next_state.cash_balance, 2) == 10_088.0
    assert round(next_state.realized_pnl, 2) == 8.0
    assert round(next_state.positions["AAPLx"].quantity, 2) == 0.6
    assert round(summary["unrealized_pnl"], 2) == 15.0
    assert round(summary["nav"], 2) == 10_223.0
```

- [ ] **Step 2: 运行测试，确认当前缺少 alpha 账本模块**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_ledger.py::test_apply_manual_fill_updates_cash_positions_and_realized_pnl -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha.ledger'
```

- [ ] **Step 3: 写最小实现，提供不可变风格的 alpha 账本函数**

```python
# src/alpha/ledger.py
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlphaPositionState:
    symbol: str
    quantity: float
    avg_cost: float


@dataclass(frozen=True)
class AlphaPortfolioState:
    cash_balance: float
    realized_pnl: float
    positions: dict[str, AlphaPositionState] = field(default_factory=dict)


def apply_manual_fill(
    state: AlphaPortfolioState,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
) -> AlphaPortfolioState:
    positions = dict(state.positions)
    current = positions.get(symbol, AlphaPositionState(symbol=symbol, quantity=0.0, avg_cost=0.0))
    cash_balance = state.cash_balance
    realized_pnl = state.realized_pnl

    if side == "BUY":
        total_cost = current.quantity * current.avg_cost + quantity * price
        new_quantity = current.quantity + quantity
        positions[symbol] = AlphaPositionState(
            symbol=symbol,
            quantity=new_quantity,
            avg_cost=(total_cost / new_quantity) if new_quantity else 0.0,
        )
        cash_balance -= quantity * price
    else:
        realized_pnl += (price - current.avg_cost) * quantity
        new_quantity = max(current.quantity - quantity, 0.0)
        positions[symbol] = AlphaPositionState(symbol=symbol, quantity=new_quantity, avg_cost=current.avg_cost)
        cash_balance += quantity * price

    return AlphaPortfolioState(
        cash_balance=cash_balance,
        realized_pnl=realized_pnl,
        positions=positions,
    )


def mark_to_market(state: AlphaPortfolioState, prices: dict[str, float]) -> dict:
    unrealized = 0.0
    market_value = 0.0
    for symbol, position in state.positions.items():
        mark_price = prices.get(symbol, position.avg_cost)
        market_value += position.quantity * mark_price
        unrealized += (mark_price - position.avg_cost) * position.quantity
    return {
        "cash_balance": state.cash_balance,
        "realized_pnl": state.realized_pnl,
        "unrealized_pnl": unrealized,
        "nav": state.cash_balance + market_value,
    }
```

- [ ] **Step 4: 运行测试，确认账本计算稳定**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_ledger.py::test_apply_manual_fill_updates_cash_positions_and_realized_pnl -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/ledger.py tests/test_alpha_ledger.py
git commit -m "feat: add alpha ledger primitives"
```

---

### Task 2: 为 alpha 持仓、组合快照和对账结果建立持久化模型

**Files:**
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_runtime_store.py`

- [ ] **Step 1: 写失败测试，锁定 alpha 组合快照和对账结果的存储合同**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_alpha_portfolio_and_reconciliation_records(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.replace_alpha_positions(
        [
            {"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0},
            {"symbol": "SPYx", "quantity": 2.0, "avg_cost": 500.0, "mark_price": 504.0},
        ]
    )
    snapshot_id = store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=36.8,
        nav=10_314.8,
    )
    run_id = store.insert_alpha_reconciliation_run(
        source="manual",
        status="MISMATCH",
        discrepancies={"AAPLx": {"internal": 1.2, "external": 1.0}},
    )

    positions = store.list_alpha_positions()
    snapshot = store.get_latest_alpha_portfolio_snapshot()
    runs = store.list_alpha_reconciliation_runs()

    assert len(positions) == 2
    assert positions[0]["symbol"] in {"AAPLx", "SPYx"}
    assert snapshot["snapshot_id"] == snapshot_id
    assert snapshot["nav"] == 10_314.8
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "MISMATCH"
```

- [ ] **Step 2: 运行测试，确认 runtime store 还没有 alpha 组合接口**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_portfolio_and_reconciliation_records -q
```

Expected:

```text
E   AttributeError: 'RuntimeStore' object has no attribute 'replace_alpha_positions'
```

- [ ] **Step 3: 写最小实现，新增 alpha 持仓表、组合快照表和对账记录表**

```python
# src/storage/models.py
class AlphaPositionRow(Base):
    __tablename__ = "alpha_positions"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    mark_price: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AlphaPortfolioSnapshotRow(Base):
    __tablename__ = "alpha_portfolio_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AlphaReconciliationRunRow(Base):
    __tablename__ = "alpha_reconciliation_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    discrepancies_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/storage/runtime_store.py
def replace_alpha_positions(self, positions: list[dict]) -> None:
    with self.engine.begin() as conn:
        conn.execute(AlphaPositionRow.__table__.delete())
        for position in positions:
            conn.execute(
                AlphaPositionRow.__table__.insert().values(
                    symbol=position["symbol"],
                    quantity=position["quantity"],
                    avg_cost=position["avg_cost"],
                    mark_price=position["mark_price"],
                )
            )


def list_alpha_positions(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(select(AlphaPositionRow).order_by(AlphaPositionRow.symbol)).fetchall()
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
                cash_balance=cash_balance,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                nav=nav,
            )
        )
    return snapshot_id


def get_latest_alpha_portfolio_snapshot(self) -> dict | None:
    with self.engine.begin() as conn:
        row = conn.execute(
            select(AlphaPortfolioSnapshotRow).order_by(AlphaPortfolioSnapshotRow.created_at.desc()).limit(1)
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


def insert_alpha_reconciliation_run(self, source: str, status: str, discrepancies: dict) -> str:
    run_id = f"alpha-recon-{uuid.uuid4().hex[:12]}"
    with self.engine.begin() as conn:
        conn.execute(
            AlphaReconciliationRunRow.__table__.insert().values(
                run_id=run_id,
                source=source,
                status=status,
                discrepancies_json=json.dumps(discrepancies, ensure_ascii=True, sort_keys=True),
            )
        )
    return run_id


def list_alpha_reconciliation_runs(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(AlphaReconciliationRunRow).order_by(AlphaReconciliationRunRow.created_at.desc())
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
```

- [ ] **Step 4: 运行测试，确认 alpha 组合持久化能力可用**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_portfolio_and_reconciliation_records -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/models.py src/storage/runtime_store.py tests/test_alpha_runtime_store.py
git commit -m "feat: persist alpha portfolio and reconciliation state"
```

---

### Task 3: 用人工成交回填重建 alpha 组合

**Files:**
- Create: `src/alpha/portfolio_service.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_portfolio_service.py`

- [ ] **Step 1: 写失败测试，锁定从 manual fills 重建组合快照的合同**

```python
from sqlalchemy import create_engine

from src.alpha.portfolio_service import AlphaPortfolioService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_portfolio_service_rebuilds_positions_from_manual_fills(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="phase2 seed",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0},
        ticket_lookup={ticket_id: {"asset_symbol": "AAPLx", "action": "BUY"}},
    )

    assert round(summary["cash_balance"], 2) == 9_600.0
    assert round(summary["unrealized_pnl"], 2) == 20.0
    assert round(summary["nav"], 2) == 10_020.0
    assert summary["positions"][0]["symbol"] == "AAPLx"
```

- [ ] **Step 2: 运行测试，确认当前缺少组合重建 service**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_portfolio_service.py::test_portfolio_service_rebuilds_positions_from_manual_fills -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha.portfolio_service'
```

- [ ] **Step 3: 写最小实现，读取 manual fills、重建组合并落快照**

```python
# src/storage/runtime_store.py
def list_all_alpha_manual_fills(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(AlphaManualFillRow).order_by(AlphaManualFillRow.created_at)
        ).fetchall()
        return [
            {
                "fill_id": row.fill_id,
                "ticket_id": row.ticket_id,
                "operator_id": row.operator_id,
                "executed_quantity": row.executed_quantity,
                "executed_price": row.executed_price,
                "notes": row.notes,
                "created_at": _cst_iso(row.created_at),
            }
            for row in rows
        ]
```

```python
# src/alpha/portfolio_service.py
from src.alpha.ledger import AlphaPortfolioState, apply_manual_fill, mark_to_market


class AlphaPortfolioService:
    def __init__(self, store) -> None:
        self._store = store

    def rebuild_from_manual_fills(
        self,
        opening_cash: float,
        price_map: dict[str, float],
        ticket_lookup: dict[str, dict],
    ) -> dict:
        state = AlphaPortfolioState(cash_balance=opening_cash, realized_pnl=0.0, positions={})
        for fill in self._store.list_all_alpha_manual_fills():
            ticket = ticket_lookup[fill["ticket_id"]]
            state = apply_manual_fill(
                state,
                symbol=ticket["asset_symbol"],
                side=ticket["action"],
                quantity=fill["executed_quantity"],
                price=fill["executed_price"],
            )

        summary = mark_to_market(state, price_map)
        positions = [
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "avg_cost": position.avg_cost,
                "mark_price": price_map.get(position.symbol, position.avg_cost),
            }
            for position in state.positions.values()
            if position.quantity > 0
        ]
        self._store.replace_alpha_positions(positions)
        self._store.insert_alpha_portfolio_snapshot(**summary)
        summary["positions"] = positions
        return summary
```

- [ ] **Step 4: 运行测试，确认组合重建与快照写入正常**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_portfolio_service.py::test_portfolio_service_rebuilds_positions_from_manual_fills -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/portfolio_service.py src/storage/runtime_store.py tests/test_alpha_portfolio_service.py
git commit -m "feat: rebuild alpha portfolio from manual fills"
```

---

### Task 4: 建立 alpha 对账服务与 API

**Files:**
- Create: `src/alpha/reconciliation.py`
- Modify: `src/api/routes_alpha.py`
- Test: `tests/test_alpha_reconciliation.py`
- Test: `tests/test_alpha_routes.py`

- [ ] **Step 1: 写失败测试，锁定 external snapshot 对比合同**

```python
from fastapi.testclient import TestClient

from src.alpha.reconciliation import reconcile_alpha_positions


def test_reconcile_alpha_positions_detects_quantity_and_cash_drift():
    result = reconcile_alpha_positions(
        internal_positions={"AAPLx": 1.2, "SPYx": 2.0},
        external_positions={"AAPLx": 1.0, "SPYx": 2.0},
        internal_cash=8_500.0,
        external_cash=8_420.0,
    )

    assert result["status"] == "MISMATCH"
    assert "AAPLx" in result["discrepancies"]["positions"]
    assert result["discrepancies"]["cash"]["difference"] == 80.0


def test_alpha_reconciliation_route_returns_run_id(test_app, pg_store):
    pg_store.replace_alpha_positions(
        [{"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0}]
    )
    pg_store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=28.8,
        nav=8_798.8,
    )
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/alpha/reconciliation/run",
        json={"external_positions": {"AAPLx": 1.0}, "external_cash": 8_420.0},
    )

    assert response.status_code == 200
    assert response.json()["run_id"].startswith("alpha-recon-")
    assert response.json()["status"] == "MISMATCH"
```

- [ ] **Step 2: 运行测试，确认当前缺少 alpha 对账模块**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_reconciliation.py::test_reconcile_alpha_positions_detects_quantity_and_cash_drift tests/test_alpha_routes.py::test_alpha_reconciliation_route_returns_run_id -q
```

Expected:

```text
2 failed
```

- [ ] **Step 3: 写最小实现，提供对账函数和路由**

```python
# src/alpha/reconciliation.py
def reconcile_alpha_positions(
    internal_positions: dict[str, float],
    external_positions: dict[str, float],
    internal_cash: float,
    external_cash: float,
) -> dict:
    position_diff = {}
    for symbol in sorted(set(internal_positions) | set(external_positions)):
        internal_qty = internal_positions.get(symbol, 0.0)
        external_qty = external_positions.get(symbol, 0.0)
        if internal_qty != external_qty:
            position_diff[symbol] = {
                "internal": internal_qty,
                "external": external_qty,
                "difference": internal_qty - external_qty,
            }

    cash_diff = {
        "internal": internal_cash,
        "external": external_cash,
        "difference": round(internal_cash - external_cash, 2),
    }
    has_cash_drift = cash_diff["difference"] != 0.0
    status = "MATCHED" if not position_diff and not has_cash_drift else "MISMATCH"
    return {"status": status, "discrepancies": {"positions": position_diff, "cash": cash_diff}}
```

```python
# src/api/routes_alpha.py
from fastapi import APIRouter, Depends

from src.alpha.reconciliation import reconcile_alpha_positions
from src.storage.dependencies import get_runtime_store


@router.post("/reconciliation/run")
def run_alpha_reconciliation(payload: dict, store=Depends(get_runtime_store)) -> dict:
    latest = store.get_latest_alpha_portfolio_snapshot() or {
        "cash_balance": 0.0,
    }
    internal_positions = {row["symbol"]: row["quantity"] for row in store.list_alpha_positions()}
    result = reconcile_alpha_positions(
        internal_positions=internal_positions,
        external_positions=payload["external_positions"],
        internal_cash=latest["cash_balance"],
        external_cash=payload["external_cash"],
    )
    run_id = store.insert_alpha_reconciliation_run(
        source="manual",
        status=result["status"],
        discrepancies=result["discrepancies"],
    )
    return {"run_id": run_id, **result}
```

- [ ] **Step 4: 运行测试，确认对账结果能被 API 返回**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_reconciliation.py::test_reconcile_alpha_positions_detects_quantity_and_cash_drift tests/test_alpha_routes.py::test_alpha_reconciliation_route_returns_run_id -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/reconciliation.py src/api/routes_alpha.py tests/test_alpha_reconciliation.py tests/test_alpha_routes.py
git commit -m "feat: add alpha reconciliation service and route"
```

---

### Task 5: 将组合、PnL 和异常汇总并入 dashboard

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/dashboard.html`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: 写失败测试，锁定 workbench alpha 组合与异常摘要**

```python
from fastapi.testclient import TestClient


def test_workbench_payload_includes_alpha_portfolio_and_exceptions(test_app, pg_store):
    pg_store.replace_alpha_positions(
        [{"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0}]
    )
    pg_store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=28.8,
        nav=8_798.8,
    )
    pg_store.insert_alpha_reconciliation_run(
        source="manual",
        status="MISMATCH",
        discrepancies={"positions": {"AAPLx": {"internal": 1.2, "external": 1.0}}},
    )
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert payload["alpha"]["portfolio"]["snapshot"]["nav"] == 8_798.8
    assert payload["alpha"]["exceptions"]["latest_status"] == "MISMATCH"
```

- [ ] **Step 2: 运行测试，确认当前 workbench 还没有组合和异常区块**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_portfolio_and_exceptions -q
```

Expected:

```text
E   KeyError: 'portfolio'
```

- [ ] **Step 3: 写最小实现，把 alpha 组合和异常区块加入 payload 和 UI**

```python
# src/api/routes_dashboard.py
def _build_alpha_panel_payload(store) -> dict:
    tickets = store.list_alpha_tickets()
    latest_ticket_id = tickets[0]["ticket_id"] if tickets else None
    latest_snapshot = store.get_latest_alpha_portfolio_snapshot()
    recon_runs = store.list_alpha_reconciliation_runs()
    latest_recon = recon_runs[0] if recon_runs else None
    return {
        "tickets": tickets,
        "fills": store.list_alpha_manual_fills(ticket_id=latest_ticket_id) if latest_ticket_id else [],
        "portfolio": {
            "positions": store.list_alpha_positions(),
            "snapshot": latest_snapshot,
        },
        "exceptions": {
            "latest_status": latest_recon["status"] if latest_recon else "UNKNOWN",
            "latest_discrepancies": latest_recon["discrepancies"] if latest_recon else {},
        },
    }
```

```html
<!-- src/api/dashboard.html -->
<div class="risk-card">
  <div class="risk-label">Alpha 组合</div>
  <div id="alpha-portfolio-summary"></div>
  <div id="alpha-positions"></div>
</div>
<div class="risk-card">
  <div class="risk-label">Alpha 异常</div>
  <div id="alpha-exceptions"></div>
</div>
<script>
function renderAlphaPortfolio(portfolio) {
  const summary = portfolio?.snapshot;
  const positions = portfolio?.positions || [];
  document.getElementById('alpha-portfolio-summary').innerHTML = summary
    ? `NAV: ${summary.nav} | Realized: ${summary.realized_pnl} | Unrealized: ${summary.unrealized_pnl}`
    : '暂无组合快照';
  document.getElementById('alpha-positions').innerHTML = positions.length
    ? positions.map((item) => `<div>${item.symbol} ${item.quantity} @ ${item.mark_price}</div>`).join('')
    : '暂无持仓';
}

function renderAlphaExceptions(exceptions) {
  document.getElementById('alpha-exceptions').innerHTML =
    exceptions?.latest_status === 'MISMATCH'
      ? JSON.stringify(exceptions.latest_discrepancies)
      : '无异常';
}
</script>
```

- [ ] **Step 4: 运行测试，确认 dashboard 能展示组合和异常摘要**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_portfolio_and_exceptions tests/test_dashboard_alpha_tab.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py src/api/dashboard.html tests/test_dashboard_api.py tests/test_dashboard_alpha_tab.py
git commit -m "feat: add alpha portfolio and exception views"
```

---

### Task 6: 运行 Phase 2 回归并补 runbook

**Files:**
- Create: `docs/runbooks/alpha-ledger-and-reconciliation.md`
- Modify: `README.md`
- Test: `tests/test_alpha_ledger.py`
- Test: `tests/test_alpha_portfolio_service.py`
- Test: `tests/test_alpha_reconciliation.py`
- Test: `tests/test_alpha_runtime_store.py`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: 写运行说明，明确组合重建和手工对账流程**

```markdown
# Alpha Ledger And Reconciliation Runbook

1. 完成 Phase 1，确保 alpha ticket 和 manual fill 已可写入。
2. 通过组合重建接口或后台任务生成最新 alpha 组合快照。
3. 录入外部现金和持仓快照，运行 `/api/v1/alpha/reconciliation/run`。
4. 若返回 `MISMATCH`，在 dashboard 的 alpha 异常区确认差异并记录处理结论。
```

- [ ] **Step 2: 运行 Phase 2 核心测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_ledger.py::test_apply_manual_fill_updates_cash_positions_and_realized_pnl tests/test_alpha_portfolio_service.py::test_portfolio_service_rebuilds_positions_from_manual_fills tests/test_alpha_reconciliation.py::test_reconcile_alpha_positions_detects_quantity_and_cash_drift tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_portfolio_and_reconciliation_records tests/test_alpha_routes.py::test_alpha_reconciliation_route_returns_run_id tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_portfolio_and_exceptions -q
```

Expected:

```text
6 passed
```

- [ ] **Step 3: 手动启动服务并检查关键接口**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 4: 用 curl 验证 alpha 组合和对账接口**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/dashboard/workbench | head -c 400
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/reconciliation/run -H 'Content-Type: application/json' -d '{"external_positions":{"AAPLx":1.0},"external_cash":8420.0}' | head -c 400
```

Expected:

```text
workbench json contains alpha portfolio
reconciliation json contains status and discrepancies
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add README.md docs/runbooks src tests
git commit -m "docs: add alpha ledger and reconciliation runbook"
```
