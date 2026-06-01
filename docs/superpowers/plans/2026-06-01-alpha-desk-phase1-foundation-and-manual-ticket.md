# Alpha Desk Phase 1 Foundation And Manual Ticket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Binance alpha 代币化证券建立第一条可用纵切面：公开资产数据、标准化建议单、人工确认与执行回填、以及 dashboard alpha 操作区。

**Architecture:** 新建 `src/alpha/` 作为 alpha 证券的独立边界，不把错误的 spot/testnet 语义继续塞进现有 `src/crypto/`。运行时存储新增 alpha ticket 与 manual fill 表，dashboard 通过新的 alpha API 读取资产、建议单和执行摘要，形成最小人工执行闭环。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, httpx, pytest

---

## 文件结构

```
a-share-hub/
├── src/
│   ├── alpha/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── binance_public_client.py
│   │   └── service.py
│   ├── api/
│   │   ├── routes_alpha.py
│   │   ├── routes_dashboard.py
│   │   └── dashboard.html
│   ├── storage/
│   │   ├── models.py
│   │   └── runtime_store.py
│   └── main.py
└── tests/
    ├── test_alpha_client.py
    ├── test_alpha_routes.py
    ├── test_alpha_runtime_store.py
    ├── test_dashboard_alpha_tab.py
    └── test_dashboard_api.py
```

---

### Task 1: 建立 alpha 公共数据模型与客户端

**Files:**
- Create: `src/alpha/__init__.py`
- Create: `src/alpha/models.py`
- Create: `src/alpha/binance_public_client.py`
- Create: `src/alpha/service.py`
- Test: `tests/test_alpha_client.py`

- [ ] **Step 1: 写失败测试，锁定 alpha 资产快照的标准化合同**

```python
import pytest

from src.alpha.service import AlphaMarketService


class FakeAlphaClient:
    async def get_tokenized_securities(self) -> dict:
        return {
            "data": {
                "tokenizedStocks": [
                    {
                        "symbol": "AAPLx",
                        "underlyingSymbol": "AAPL",
                        "projectId": "alpha-aaplx",
                        "marketStatus": "TRADING",
                        "assetStatus": "ACTIVE",
                        "sharesMultiplier": "1",
                        "limitInfo": {"minQty": "0.1", "maxQty": "50"},
                    }
                ]
            }
        }


@pytest.mark.asyncio
async def test_market_service_normalizes_asset_snapshot():
    service = AlphaMarketService(FakeAlphaClient())

    snapshots = await service.list_asset_snapshots()

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.symbol == "AAPLx"
    assert snapshot.underlying_symbol == "AAPL"
    assert snapshot.market_status == "TRADING"
    assert snapshot.asset_status == "ACTIVE"
    assert snapshot.shares_multiplier == 1.0
    assert snapshot.min_qty == 0.1
    assert snapshot.max_qty == 50.0
```

- [ ] **Step 2: 运行测试，确认当前缺少 alpha service**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_client.py::test_market_service_normalizes_asset_snapshot -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha'
```

- [ ] **Step 3: 写最小实现，提供 alpha 模型、客户端接口和归一化 service**

```python
# src/alpha/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaAssetSnapshot:
    symbol: str
    underlying_symbol: str
    project_id: str
    market_status: str
    asset_status: str
    shares_multiplier: float
    min_qty: float | None
    max_qty: float | None


# src/alpha/binance_public_client.py
import httpx


class BinanceAlphaPublicClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_tokenized_securities(self) -> dict:
        response = await self._http.get("/bapi/defi/v1/public/alpha-trade/tokenized-securities/list")
        response.raise_for_status()
        return response.json()


# src/alpha/service.py
from src.alpha.models import AlphaAssetSnapshot


class AlphaMarketService:
    def __init__(self, client) -> None:
        self._client = client

    async def list_asset_snapshots(self) -> list[AlphaAssetSnapshot]:
        payload = await self._client.get_tokenized_securities()
        rows = payload.get("data", {}).get("tokenizedStocks", [])
        return [
            AlphaAssetSnapshot(
                symbol=row["symbol"],
                underlying_symbol=row.get("underlyingSymbol", ""),
                project_id=row.get("projectId", row["symbol"]),
                market_status=row.get("marketStatus", "UNKNOWN"),
                asset_status=row.get("assetStatus", "UNKNOWN"),
                shares_multiplier=float(row.get("sharesMultiplier", "1")),
                min_qty=float(row["limitInfo"]["minQty"]) if row.get("limitInfo", {}).get("minQty") else None,
                max_qty=float(row["limitInfo"]["maxQty"]) if row.get("limitInfo", {}).get("maxQty") else None,
            )
            for row in rows
        ]
```

- [ ] **Step 4: 运行测试，确认标准化合同通过**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_client.py::test_market_service_normalizes_asset_snapshot -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha tests/test_alpha_client.py
git commit -m "feat: add alpha public market foundation"
```

---

### Task 2: 暴露 alpha 只读 API，并把主服务接上

**Files:**
- Create: `src/api/routes_alpha.py`
- Modify: `src/main.py`
- Test: `tests/test_alpha_routes.py`

- [ ] **Step 1: 写失败测试，锁定 alpha 资产列表接口**

```python
from fastapi.testclient import TestClient

from src.main import build_app


def test_alpha_assets_endpoint_returns_normalized_rows(monkeypatch):
    from src.api import routes_alpha

    class FakeService:
        async def list_asset_snapshots(self):
            from src.alpha.models import AlphaAssetSnapshot

            return [
                AlphaAssetSnapshot(
                    symbol="AAPLx",
                    underlying_symbol="AAPL",
                    project_id="alpha-aaplx",
                    market_status="TRADING",
                    asset_status="ACTIVE",
                    shares_multiplier=1.0,
                    min_qty=0.1,
                    max_qty=50.0,
                )
            ]

    monkeypatch.setattr(routes_alpha, "_get_alpha_market_service", lambda: FakeService())
    client = TestClient(build_app())

    response = client.get("/api/v1/alpha/assets")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["symbol"] == "AAPLx"
    assert body["items"][0]["market_status"] == "TRADING"
```

- [ ] **Step 2: 运行测试，确认路由尚未注册**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_assets_endpoint_returns_normalized_rows -q
```

Expected:

```text
E   ImportError: cannot import name 'routes_alpha'
```

- [ ] **Step 3: 写最小实现，提供 alpha 只读 API 并注册到应用**

```python
# src/api/routes_alpha.py
from fastapi import APIRouter

from src.alpha.binance_public_client import BinanceAlphaPublicClient
from src.alpha.service import AlphaMarketService

router = APIRouter(prefix="/api/v1/alpha", tags=["alpha"])
_service: AlphaMarketService | None = None


def _get_alpha_market_service() -> AlphaMarketService:
    global _service
    if _service is None:
        import httpx

        client = httpx.AsyncClient(base_url="https://www.binance.com")
        _service = AlphaMarketService(BinanceAlphaPublicClient(client))
    return _service


@router.get("/assets")
async def list_alpha_assets() -> dict:
    snapshots = await _get_alpha_market_service().list_asset_snapshots()
    return {
        "items": [
            {
                "symbol": item.symbol,
                "underlying_symbol": item.underlying_symbol,
                "project_id": item.project_id,
                "market_status": item.market_status,
                "asset_status": item.asset_status,
                "shares_multiplier": item.shares_multiplier,
                "min_qty": item.min_qty,
                "max_qty": item.max_qty,
            }
            for item in snapshots
        ]
    }


# src/main.py
from src.api.routes_alpha import router as alpha_router
from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_crypto import router as crypto_router
from src.api.routes_dashboard import router as dashboard_router
from src.api.routes_decision_runs import router as decision_runs_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.api.routes_market import router as market_router
from src.api.routes_portfolio_targets import router as portfolio_targets_router
from src.api.routes_reconciliation import router as reconciliation_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(decision_runs_router)
    app.include_router(portfolio_targets_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(reconciliation_router)
    app.include_router(kill_switch_router)
    app.include_router(market_router)
    app.include_router(dashboard_router)
    app.include_router(alpha_router)
    app.include_router(crypto_router)
    return app
```

- [ ] **Step 4: 运行测试，确认 alpha 只读接口可用**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_assets_endpoint_returns_normalized_rows -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_alpha.py src/main.py tests/test_alpha_routes.py
git commit -m "feat: add alpha public api routes"
```

---

### Task 3: 为建议单和人工执行回填建立权威存储

**Files:**
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_runtime_store.py`

- [ ] **Step 1: 写失败测试，锁定建议单与回填写入合同**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_alpha_ticket_and_manual_fill(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="discount to reference",
        suggested_quantity=2.0,
        suggested_limit_price=210.5,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.approve_alpha_ticket(ticket_id=ticket_id, operator_id="trader-01")
    fill_id = store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=210.2,
        notes="filled manually in app",
    )

    tickets = store.list_alpha_tickets()
    fills = store.list_alpha_manual_fills(ticket_id=ticket_id)

    assert tickets[0]["ticket_id"] == ticket_id
    assert tickets[0]["status"] == "APPROVED"
    assert fills[0]["fill_id"] == fill_id
    assert fills[0]["executed_price"] == 210.2
```

- [ ] **Step 2: 运行测试，确认 store 还没有 alpha 票据接口**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_ticket_and_manual_fill -q
```

Expected:

```text
E   AttributeError: 'RuntimeStore' object has no attribute 'insert_alpha_ticket'
```

- [ ] **Step 3: 写最小实现，新增 alpha_ticket 和 alpha_manual_fill 表与 store 方法**

```python
# src/storage/models.py
class AlphaTicketRow(Base):
    __tablename__ = "alpha_tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AlphaManualFillRow(Base):
    __tablename__ = "alpha_manual_fills"

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    executed_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# src/storage/runtime_store.py
def insert_alpha_ticket(
    self,
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


def approve_alpha_ticket(self, ticket_id: str, operator_id: str) -> None:
    with self.engine.begin() as conn:
        conn.execute(
            AlphaTicketRow.__table__.update()
            .where(AlphaTicketRow.ticket_id == ticket_id)
            .values(status="APPROVED", approved_by=operator_id)
        )


def insert_alpha_manual_fill(
    self,
    ticket_id: str,
    operator_id: str,
    executed_quantity: float,
    executed_price: float,
    notes: str,
) -> str:
    fill_id = f"alpha-fill-{uuid.uuid4().hex[:12]}"
    with self.engine.begin() as conn:
        conn.execute(
            AlphaManualFillRow.__table__.insert().values(
                fill_id=fill_id,
                ticket_id=ticket_id,
                operator_id=operator_id,
                executed_quantity=executed_quantity,
                executed_price=executed_price,
                notes=notes,
            )
        )
    return fill_id


def list_alpha_tickets(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(select(AlphaTicketRow).order_by(AlphaTicketRow.created_at.desc())).fetchall()
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


def list_alpha_manual_fills(self, ticket_id: str) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(AlphaManualFillRow)
            .where(AlphaManualFillRow.ticket_id == ticket_id)
            .order_by(AlphaManualFillRow.created_at.desc())
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

- [ ] **Step 4: 运行测试，确认 alpha 票据闭环可以持久化**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_ticket_and_manual_fill -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/models.py src/storage/runtime_store.py tests/test_alpha_runtime_store.py
git commit -m "feat: add alpha ticket runtime storage"
```

---

### Task 4: 暴露建议单与人工回填 API，并并入 dashboard workbench

**Files:**
- Modify: `src/api/routes_alpha.py`
- Modify: `src/api/routes_dashboard.py`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: 写失败测试，锁定建议单 API 与 workbench alpha 合同**

```python
from fastapi.testclient import TestClient


def test_alpha_ticket_api_supports_create_approve_and_fill(test_app):
    client = TestClient(test_app)

    create_res = client.post(
        "/api/v1/alpha/tickets",
        json={
            "asset_symbol": "AAPLx",
            "underlying_symbol": "AAPL",
            "action": "BUY",
            "thesis": "discount to reference",
            "suggested_quantity": 2.0,
            "suggested_limit_price": 210.5,
            "expires_at": "2026-06-01T16:00:00+08:00",
        },
    )
    ticket_id = create_res.json()["ticket_id"]

    approve_res = client.post(f"/api/v1/alpha/tickets/{ticket_id}/approve", json={"operator_id": "trader-01"})
    fill_res = client.post(
        f"/api/v1/alpha/tickets/{ticket_id}/fills",
        json={
            "operator_id": "trader-01",
            "executed_quantity": 2.0,
            "executed_price": 210.2,
            "notes": "filled manually",
        },
    )
    workbench_res = client.get("/api/v1/dashboard/workbench")

    assert create_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"
    assert fill_res.json()["recorded"] is True
    assert "alpha" in workbench_res.json()
    assert workbench_res.json()["alpha"]["tickets"][0]["asset_symbol"] == "AAPLx"


def test_workbench_payload_includes_alpha_panel(test_app, pg_store):
    ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="discount to reference",
        suggested_quantity=2.0,
        suggested_limit_price=210.5,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert "alpha" in payload
    assert payload["alpha"]["tickets"][0]["ticket_id"] == ticket_id
```

- [ ] **Step 2: 运行测试，确认当前没有 alpha ticket 行为**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_ticket_api_supports_create_approve_and_fill -q
```

Expected:

```text
E   assert 404 == 200
```

- [ ] **Step 3: 写最小实现，补齐 ticket/fill API 并将 alpha 摘要并入 workbench**

```python
# src/api/routes_alpha.py
@router.post("/tickets")
def create_alpha_ticket(payload: dict, store=Depends(get_runtime_store)) -> dict:
    ticket_id = store.insert_alpha_ticket(**payload)
    return {"ticket_id": ticket_id, "status": "PROPOSED"}


@router.post("/tickets/{ticket_id}/approve")
def approve_alpha_ticket(ticket_id: str, payload: dict, store=Depends(get_runtime_store)) -> dict:
    store.approve_alpha_ticket(ticket_id=ticket_id, operator_id=payload["operator_id"])
    return {"ticket_id": ticket_id, "status": "APPROVED"}


@router.post("/tickets/{ticket_id}/fills")
def record_alpha_fill(ticket_id: str, payload: dict, store=Depends(get_runtime_store)) -> dict:
    fill_id = store.insert_alpha_manual_fill(ticket_id=ticket_id, **payload)
    return {"ticket_id": ticket_id, "fill_id": fill_id, "recorded": True}


# src/api/routes_dashboard.py
def _build_alpha_panel_payload(store) -> dict:
    tickets = store.list_alpha_tickets()
    latest_ticket_id = tickets[0]["ticket_id"] if tickets else None
    return {
        "tickets": tickets,
        "fills": store.list_alpha_manual_fills(ticket_id=latest_ticket_id) if latest_ticket_id else [],
    }


def get_workbench(store=Depends(get_runtime_store)) -> dict:
    payload = _build_workbench_payload(store)
    payload["alpha"] = _build_alpha_panel_payload(store)
    return payload
```

- [ ] **Step 4: 运行测试，确认 API 和 workbench 已打通**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_ticket_api_supports_create_approve_and_fill tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_panel -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_alpha.py src/api/routes_dashboard.py tests/test_alpha_routes.py tests/test_dashboard_api.py
git commit -m "feat: add alpha ticket api and dashboard payload"
```

---

### Task 5: 将 dashboard 的 crypto 区改成 alpha 操作区

**Files:**
- Modify: `src/api/dashboard.html`
- Test: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: 写失败测试，锁定 alpha 操作区的最小 UI 合同**

```python
from pathlib import Path


def test_dashboard_contains_alpha_operations_tab():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "view-alpha" in content
    assert "Alpha 代币化证券" in content
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in content
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in content
    assert "renderAlphaTickets" in content
    assert "submitAlphaTicket" in content
```

- [ ] **Step 2: 运行测试，确认当前还是 crypto 监控块**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_operations_tab -q
```

Expected:

```text
E   AssertionError: assert 'view-alpha' in content
```

- [ ] **Step 3: 写最小实现，把静态 crypto 卡片改成 alpha 操作区**

```html
<!-- src/api/dashboard.html -->
<div class="view" id="view-alpha">
  <h2>Alpha 代币化证券</h2>
  <div class="risk-card">
    <div class="risk-label">资产状态</div>
    <div id="alpha-assets"></div>
  </div>
  <div class="risk-card">
    <div class="risk-label">建议单</div>
    <form id="alpha-ticket-form" onsubmit="submitAlphaTicket(event)">
      <input id="alpha-symbol" />
      <input id="alpha-underlying" />
      <input id="alpha-qty" />
      <input id="alpha-limit" />
      <textarea id="alpha-thesis"></textarea>
      <button type="submit">创建建议单</button>
    </form>
    <div id="alpha-tickets"></div>
  </div>
</div>
<script>
const ALPHA_ASSETS_API = '/api/v1/alpha/assets';
const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';

function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  if (!items.length) {
    root.innerHTML = '<span style="color:var(--dim)">暂无建议单</span>';
    return;
  }
  root.innerHTML = items.map((item) => `
    <div class="ticket-row">
      <strong>${item.asset_symbol}</strong>
      <span>${item.action}</span>
      <span>${item.suggested_quantity}</span>
      <span>@ ${item.suggested_limit_price}</span>
      <span>${item.status}</span>
    </div>
  `).join('');
}

async function submitAlphaTicket(event) {
  event.preventDefault();
  const payload = {
    asset_symbol: document.getElementById('alpha-symbol').value.trim(),
    underlying_symbol: document.getElementById('alpha-underlying').value.trim(),
    action: 'BUY',
    thesis: document.getElementById('alpha-thesis').value.trim(),
    suggested_quantity: Number(document.getElementById('alpha-qty').value),
    suggested_limit_price: Number(document.getElementById('alpha-limit').value),
    expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
  };
  const response = await fetch(ALPHA_TICKETS_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error('alpha ticket create failed');
  }
  const workbench = await fetch(WORKBENCH_API).then((res) => res.json());
  renderAlphaTickets(workbench.alpha?.tickets || []);
}
</script>
```

- [ ] **Step 4: 运行测试，确认 dashboard 结构完成切换**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_operations_tab -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard.html tests/test_dashboard_alpha_tab.py
git commit -m "feat: convert crypto monitor into alpha desk panel"
```

---

### Task 6: 运行 phase 1 回归并更新文档

**Files:**
- Modify: `README.md`
- Create: `docs/runbooks/alpha-desk.md`
- Test: `tests/test_alpha_client.py`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_alpha_runtime_store.py`
- Test: `tests/test_dashboard_alpha_tab.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: 写 README 增量说明，明确 alpha desk 的边界**

```markdown
## Alpha 代币化证券操作台

- 公开资产数据通过 `/api/v1/alpha/assets` 提供
- 建议单通过 `/api/v1/alpha/tickets` 创建与查看
- 人工执行结果通过 `/api/v1/alpha/tickets/{ticket_id}/fills` 回填
- 当前版本不支持自动下单
```

- [ ] **Step 2: 运行 phase 1 相关测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_client.py::test_market_service_normalizes_asset_snapshot tests/test_alpha_routes.py::test_alpha_assets_endpoint_returns_normalized_rows tests/test_alpha_routes.py::test_alpha_ticket_api_supports_create_approve_and_fill tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_ticket_and_manual_fill tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_operations_tab tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_panel -q
```

Expected:

```text
6 passed
```

- [ ] **Step 3: 手动启动服务验证 API 路由**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 4: 访问关键页面和接口，确认第一条纵切面存在**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/alpha/assets | head -c 400
curl -s http://127.0.0.1:8000/api/v1/dashboard/workbench | head -c 400
```

Expected:

```text
alpha assets json
alpha payload present in workbench json
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add README.md docs/runbooks src tests
git commit -m "docs: document alpha desk phase 1"
```

---

## 计划外但必须记住的后续项

- phase 2 再引入基于 alpha 对象模型的建议单自动生成，不要在 phase 1 提前做 LLM 或复杂量化编排。
- phase 2 再补 alpha 持仓账本、基础 PnL 和漂移检测，不要把它和 phase 1 的 API 打通工作混在一起。
- phase 3 再考虑是否删除或收敛现有 generic crypto API 和 UI 残留。
