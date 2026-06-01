# Alpha Desk Phase 4 Execution Capability Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏手工执行主链路的前提下，为未来可能出现的 alpha 公开交易接口建立能力探测、执行适配器、受控下单入口和审计存储。

**Architecture:** 这一 phase 是条件执行计划：只有在公开交易接口文档被确认、字段和签名方式稳定后才启动。实现上新增 `execution_service` 和 `execution_gateway` 抽象，把“有没有 API 下单能力”变成一个显式 capability gate；默认模式仍然是 `manual` 或 `disabled`，只有 capability 满足时才开放 submit 路由。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, httpx, pydantic-settings, pytest

---

## 前置条件

- `docs/superpowers/plans/2026-06-01-alpha-desk-phase3-research-and-ops-ui.md` 已完成并合入。
- 已确认公开交易接口的文档地址、认证方式、下单字段、错误码和速率限制。
- 若上述条件不能满足，本计划不得开始实施。

---

## 文件结构

```
a-share-hub/
├── src/
│   ├── alpha/
│   │   ├── execution_models.py
│   │   ├── execution_gateway.py
│   │   └── execution_service.py
│   ├── api/
│   │   ├── routes_alpha.py
│   │   ├── routes_dashboard.py
│   │   └── dashboard.html
│   ├── core/
│   │   └── config.py
│   └── storage/
│       ├── models.py
│       └── runtime_store.py
└── tests/
    ├── test_alpha_execution_service.py
    ├── test_alpha_routes.py
    ├── test_alpha_runtime_store.py
    ├── test_config_env.py
    ├── test_dashboard_alpha_tab.py
    └── test_dashboard_api.py
```

---

### Task 1: 加入 alpha 执行模式配置与 capability 探针

**Files:**
- Modify: `src/core/config.py`
- Create: `src/alpha/execution_models.py`
- Test: `tests/test_config_env.py`
- Test: `tests/test_alpha_execution_service.py`

- [ ] **Step 1: 写失败测试，锁定执行模式和 capability 配置**

```python
from src.core.config import Settings


def test_settings_expose_alpha_execution_configuration(monkeypatch):
    monkeypatch.setenv("ALPHA_EXECUTION_MODE", "api")
    monkeypatch.setenv("ALPHA_API_BASE_URL", "https://example.binance.test")
    monkeypatch.setenv("ALPHA_API_KEY", "key-123")
    monkeypatch.setenv("ALPHA_API_SECRET", "secret-123")

    settings = Settings()

    assert settings.alpha_execution_mode == "api"
    assert settings.alpha_api_base_url == "https://example.binance.test"
    assert settings.alpha_api_key == "key-123"
    assert settings.alpha_api_secret == "secret-123"
```

- [ ] **Step 2: 运行测试，确认当前没有 alpha 执行配置**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py::test_settings_expose_alpha_execution_configuration -q
```

Expected:

```text
E   AttributeError: 'Settings' object has no attribute 'alpha_execution_mode'
```

- [ ] **Step 3: 写最小实现，增加执行配置和 capability 模型**

```python
# src/core/config.py
alpha_execution_mode: str = "manual"
alpha_api_base_url: str = ""
alpha_api_key: str = ""
alpha_api_secret: str = ""
```

```python
# src/alpha/execution_models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaExecutionCapability:
    mode: str
    enabled: bool
    reason: str


@dataclass(frozen=True)
class AlphaExecutionRequest:
    ticket_id: str
    asset_symbol: str
    action: str
    quantity: float
    limit_price: float
```

- [ ] **Step 4: 运行测试，确认配置可被读取**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py::test_settings_expose_alpha_execution_configuration -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/core/config.py src/alpha/execution_models.py tests/test_config_env.py tests/test_alpha_execution_service.py
git commit -m "feat: add alpha execution configuration"
```

---

### Task 2: 建立 execution gateway 抽象和 capability gate

**Files:**
- Create: `src/alpha/execution_gateway.py`
- Create: `src/alpha/execution_service.py`
- Test: `tests/test_alpha_execution_service.py`

- [ ] **Step 1: 写失败测试，锁定 disabled/manual/api 三种模式的能力合同**

```python
from src.alpha.execution_models import AlphaExecutionCapability, AlphaExecutionRequest
from src.alpha.execution_service import AlphaExecutionService


class FakeGateway:
    async def submit_limit_order(self, request: AlphaExecutionRequest) -> dict:
        return {"remote_order_id": "remote-001", "status": "SUBMITTED"}


def test_execution_service_blocks_submit_when_mode_is_manual():
    service = AlphaExecutionService(mode="manual", gateway=None)

    capability = service.get_capability()

    assert capability == AlphaExecutionCapability(mode="manual", enabled=False, reason="manual execution only")


def test_execution_service_submits_order_when_api_mode_is_enabled():
    service = AlphaExecutionService(mode="api", gateway=FakeGateway())
    request = AlphaExecutionRequest(
        ticket_id="alpha-ticket-001",
        asset_symbol="AAPLx",
        action="BUY",
        quantity=1.0,
        limit_price=210.0,
    )

    result = service.build_submission(request)

    assert result["mode"] == "api"
    assert result["asset_symbol"] == "AAPLx"
```

- [ ] **Step 2: 运行测试，确认当前缺少 execution service**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_execution_service.py::test_execution_service_blocks_submit_when_mode_is_manual -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha.execution_service'
```

- [ ] **Step 3: 写最小实现，提供 capability gate 和 submission builder**

```python
# src/alpha/execution_gateway.py
from abc import ABC, abstractmethod


class AlphaExecutionGateway(ABC):
    @abstractmethod
    async def submit_limit_order(self, request):
        raise NotImplementedError
```

```python
# src/alpha/execution_service.py
from src.alpha.execution_models import AlphaExecutionCapability


class AlphaExecutionService:
    def __init__(self, mode: str, gateway) -> None:
        self._mode = mode
        self._gateway = gateway

    def get_capability(self) -> AlphaExecutionCapability:
        if self._mode == "api" and self._gateway is not None:
            return AlphaExecutionCapability(mode="api", enabled=True, reason="remote submit enabled")
        if self._mode == "manual":
            return AlphaExecutionCapability(mode="manual", enabled=False, reason="manual execution only")
        return AlphaExecutionCapability(mode=self._mode, enabled=False, reason="execution disabled")

    def build_submission(self, request) -> dict:
        capability = self.get_capability()
        if not capability.enabled:
            return {"mode": capability.mode, "enabled": False, "reason": capability.reason}
        return {
            "mode": capability.mode,
            "enabled": True,
            "ticket_id": request.ticket_id,
            "asset_symbol": request.asset_symbol,
            "action": request.action,
            "quantity": request.quantity,
            "limit_price": request.limit_price,
        }
```

- [ ] **Step 4: 运行测试，确认 capability gate 正常工作**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_execution_service.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/execution_gateway.py src/alpha/execution_service.py tests/test_alpha_execution_service.py
git commit -m "feat: add alpha execution capability gate"
```

---

### Task 3: 为 API 提交尝试建立权威审计存储

**Files:**
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_runtime_store.py`

- [ ] **Step 1: 写失败测试，锁定 alpha API order attempt 的存储合同**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_alpha_api_order_attempt(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    attempt_id = store.insert_alpha_api_order_attempt(
        ticket_id="alpha-ticket-001",
        asset_symbol="AAPLx",
        action="BUY",
        quantity=1.0,
        limit_price=210.0,
        mode="api",
        status="SUBMITTED",
        remote_order_id="remote-001",
        response_payload={"status": "SUBMITTED"},
    )

    attempts = store.list_alpha_api_order_attempts()

    assert attempts[0]["attempt_id"] == attempt_id
    assert attempts[0]["remote_order_id"] == "remote-001"
    assert attempts[0]["status"] == "SUBMITTED"
```

- [ ] **Step 2: 运行测试，确认当前没有 alpha API order attempt 表**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_api_order_attempt -q
```

Expected:

```text
E   AttributeError: 'RuntimeStore' object has no attribute 'insert_alpha_api_order_attempt'
```

- [ ] **Step 3: 写最小实现，新增 alpha_api_order_attempts 表与 store 方法**

```python
# src/storage/models.py
class AlphaApiOrderAttemptRow(Base):
    __tablename__ = "alpha_api_order_attempts"

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    remote_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/storage/runtime_store.py
def insert_alpha_api_order_attempt(
    self,
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


def list_alpha_api_order_attempts(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(AlphaApiOrderAttemptRow).order_by(AlphaApiOrderAttemptRow.created_at.desc())
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
```

- [ ] **Step 4: 运行测试，确认 API attempt 审计存储正常**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_api_order_attempt -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/models.py src/storage/runtime_store.py tests/test_alpha_runtime_store.py
git commit -m "feat: audit alpha api order attempts"
```

---

### Task 4: 暴露 capability、preview 和 submit API

**Files:**
- Modify: `src/api/routes_alpha.py`
- Test: `tests/test_alpha_routes.py`

- [ ] **Step 1: 写失败测试，锁定 capability 和 submit 行为**

```python
from fastapi.testclient import TestClient


def test_alpha_capabilities_report_manual_mode(test_app, monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())
    client = TestClient(test_app)

    response = client.get("/api/v1/alpha/capabilities")

    assert response.status_code == 200
    assert response.json()["mode"] == "manual"


def test_alpha_submit_returns_409_when_capability_disabled(test_app, monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

        def build_submission(self, request):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/alpha/orders/submit",
        json={
            "ticket_id": "alpha-ticket-001",
            "asset_symbol": "AAPLx",
            "action": "BUY",
            "quantity": 1.0,
            "limit_price": 210.0,
        },
    )

    assert response.status_code == 409
```

- [ ] **Step 2: 运行测试，确认当前没有 capability 和 submit 路由**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_capabilities_report_manual_mode tests/test_alpha_routes.py::test_alpha_submit_returns_409_when_capability_disabled -q
```

Expected:

```text
2 failed
```

- [ ] **Step 3: 写最小实现，提供 capabilities、preview 和 submit**

```python
# src/api/routes_alpha.py
from fastapi import HTTPException
from src.alpha.execution_models import AlphaExecutionRequest


@router.get("/capabilities")
def get_alpha_capabilities() -> dict:
    capability = _get_alpha_execution_service().get_capability()
    return capability if isinstance(capability, dict) else capability.__dict__


@router.post("/orders/preview")
def preview_alpha_order(payload: dict) -> dict:
    request = AlphaExecutionRequest(**payload)
    submission = _get_alpha_execution_service().build_submission(request)
    return submission


@router.post("/orders/submit")
def submit_alpha_order(payload: dict, store=Depends(get_runtime_store)) -> dict:
    request = AlphaExecutionRequest(**payload)
    submission = _get_alpha_execution_service().build_submission(request)
    if not submission["enabled"]:
        raise HTTPException(status_code=409, detail=submission["reason"])
    attempt_id = store.insert_alpha_api_order_attempt(
        ticket_id=request.ticket_id,
        asset_symbol=request.asset_symbol,
        action=request.action,
        quantity=request.quantity,
        limit_price=request.limit_price,
        mode=submission["mode"],
        status="SUBMITTED",
        remote_order_id=None,
        response_payload=submission,
    )
    return {"attempt_id": attempt_id, **submission}
```

- [ ] **Step 4: 运行测试，确认 capability 路由和 409 行为正确**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_capabilities_report_manual_mode tests/test_alpha_routes.py::test_alpha_submit_returns_409_when_capability_disabled -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_alpha.py tests/test_alpha_routes.py
git commit -m "feat: expose alpha execution capability routes"
```

---

### Task 5: 在 dashboard 中明确 direct execution 是受控能力

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/dashboard.html`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: 写失败测试，锁定 dashboard 的 capability 状态显示**

```python
from pathlib import Path


def test_dashboard_contains_alpha_execution_capability_panel():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "alpha-execution-capability" in content
    assert "Direct Execution Capability" in content
    assert "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';" in content
```

- [ ] **Step 2: 运行测试，确认 dashboard 还没有 execution capability 面板**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_execution_capability_panel -q
```

Expected:

```text
E   AssertionError: assert 'alpha-execution-capability' in content
```

- [ ] **Step 3: 写最小实现，在 workbench 和 UI 中展示 capability**

```python
# src/api/routes_dashboard.py
def _build_alpha_panel_payload(store) -> dict:
    tickets = store.list_alpha_tickets()
    latest_ticket_id = tickets[0]["ticket_id"] if tickets else None
    latest_snapshot = store.get_latest_alpha_portfolio_snapshot()
    recon_runs = store.list_alpha_reconciliation_runs()
    latest_recon = recon_runs[0] if recon_runs else None
    capability = _get_alpha_execution_service().get_capability()
    capability_payload = capability if isinstance(capability, dict) else capability.__dict__
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
        "research": {
            "watchlist": store.list_alpha_watchlist_items(),
            "latest_candidates": [],
        },
        "execution_capability": capability_payload,
    }
```

```html
<!-- src/api/dashboard.html -->
<div class="risk-card" id="alpha-execution-capability">
  <div class="risk-label">Direct Execution Capability</div>
  <div id="alpha-execution-mode"></div>
  <div id="alpha-execution-reason"></div>
</div>
<script>
const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';

function renderAlphaExecutionCapability(capability) {
  document.getElementById('alpha-execution-mode').textContent = capability.mode;
  document.getElementById('alpha-execution-reason').textContent = capability.reason;
}
</script>
```

- [ ] **Step 4: 运行测试，确认 capability 面板存在**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_execution_capability_panel tests/test_dashboard_api.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py src/api/dashboard.html tests/test_dashboard_alpha_tab.py tests/test_dashboard_api.py
git commit -m "feat: surface alpha execution capability in dashboard"
```

---

### Task 6: 写 Phase 4 运行前检查 runbook 并执行回归

**Files:**
- Create: `docs/runbooks/alpha-execution-capability-gate.md`
- Modify: `README.md`
- Test: `tests/test_alpha_execution_service.py`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_alpha_runtime_store.py`
- Test: `tests/test_config_env.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: 写运行前检查文档，明确 Phase 4 的硬前提**

```markdown
# Alpha Execution Capability Gate Runbook

1. 先确认公开交易接口文档稳定可用。
2. 设置 `ALPHA_EXECUTION_MODE`、`ALPHA_API_BASE_URL`、`ALPHA_API_KEY`、`ALPHA_API_SECRET`。
3. 先调用 `/api/v1/alpha/capabilities`，确认 capability 为 enabled。
4. 先走 `/api/v1/alpha/orders/preview`，确认字段和签名未漂移。
5. 只有 preview 正常，才允许开放 `/api/v1/alpha/orders/submit`。
```

- [ ] **Step 2: 运行 Phase 4 核心测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py::test_settings_expose_alpha_execution_configuration tests/test_alpha_execution_service.py::test_execution_service_blocks_submit_when_mode_is_manual tests/test_alpha_execution_service.py::test_execution_service_submits_order_when_api_mode_is_enabled tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_api_order_attempt tests/test_alpha_routes.py::test_alpha_capabilities_report_manual_mode tests/test_alpha_routes.py::test_alpha_submit_returns_409_when_capability_disabled tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_execution_capability_panel -q
```

Expected:

```text
7 passed
```

- [ ] **Step 3: 启动服务并检查 capability 路由**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 4: 用 curl 验证 capability 与 preview 路由**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/alpha/capabilities | head -c 300
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/orders/preview -H 'Content-Type: application/json' -d '{"ticket_id":"alpha-ticket-001","asset_symbol":"AAPLx","action":"BUY","quantity":1.0,"limit_price":210.0}' | head -c 300
```

Expected:

```text
capability json returned
preview json returned with enabled or disabled fields
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add README.md docs/runbooks src tests
git commit -m "docs: add alpha execution capability gate runbook"
```
