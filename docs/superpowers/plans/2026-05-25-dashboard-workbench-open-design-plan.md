# 仪表盘模拟交易工作台实施计划

> **给代理执行者：** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施本计划。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 将当前静态仪表盘改造成一个可配置、可执行、可回放的 A 股模拟交易工作台，并在页面内完成 `decide -> shadow-execute -> reconcile`。

**架构：** 保持现有 `FastAPI + 单页 HTML + Vanilla JS` 架构，不引入 React/Vue，不新增平行入口。后端新增一个聚合型工作台读接口和一个模拟运行写接口，复用现有 `decision_runs / target_positions / execution_plans / execution_orders / broker_events / kill_switch_events` 作为唯一权威数据链路。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、pytest、fastapi.testclient、Vanilla JavaScript、PaperBroker、MockProvider

---

## 范围与假设

- 本计划只覆盖 `shadow` 模式，不接 `live-execute`。
- 本计划不引入 SQLite。所有新增和本次改动涉及的测试都必须跑在 PostgreSQL 上。
- 仪表盘首页不再展示无法审计的假指标，例如“总资产 / 今日盈亏 / 持仓市值”。在没有真实账本与持仓估值服务前，这些值一律不展示。
- 模拟配置不新建专用数据库表，统一复用 `decision_input_snapshots.payload_json` 记录本轮配置与风险参数。
- 当前仓库仍有历史 SQLite 测试文件；本计划不批量清洗所有历史测试，只要求本次新增和修改的测试统一切到 PostgreSQL fixture。

## 文件结构

### 现有文件

- `src/api/dashboard.html`
  当前仪表盘单页入口。最终仍保留为唯一页面入口，但要替换掉静态样例卡片和硬编码表格。

- `src/api/routes_dashboard.py`
  当前仪表盘 HTTP 读接口。最终负责返回工作台聚合数据，并接收“运行一轮模拟交易”的请求。

- `src/api/routes_kill_switch.py`
  当前停机接口。最终必须成为页面和 CLI 共用的唯一停机状态入口，负责写 `kill_switch_event`，不能只改内存状态。

- `src/storage/runtime_store.py`
  现有运行时存储。最终要补齐工作台所需的查询能力，例如执行订单历史、broker 事件历史、停机事件历史，以及工作台摘要所需的聚合方法。

- `src/main.py`
  现有 CLI 和 FastAPI 应用装配入口。最终只保留路由装配和 CLI 解析，不承担页面业务编排。

### 新建文件

- `src/runtime/command_service.py`
  从 `src/main.py` 抽离 `run_decide_command` 与 `run_halt_command`，避免页面工作台服务导入 `main.py` 造成循环依赖。

- `src/dashboard/workbench_service.py`
  工作台后端编排服务。负责：解析页面参数、去重股票代码、调用决策命令、生成执行计划/执行订单、调用 `PaperBroker`、写 broker 事件、构造本轮时间线摘要。

- `tests/conftest.py`
  提供 PostgreSQL 测试引擎、`RuntimeStore` fixture、`FastAPI` dependency override fixture。禁止新增 SQLite fixture。

- `tests/test_dashboard_api.py`
  仪表盘 HTTP 契约测试，覆盖工作台读接口、模拟运行接口、历史回放载荷、停机态展示。

- `tests/test_dashboard_workbench_service.py`
  工作台编排服务测试，覆盖一轮模拟交易落库、股票代码标准化、停机阻断、执行结果汇总。

- `tests/test_dashboard_html.py`
  仪表盘页面结构冒烟测试，验证首屏关键区块与 DOM 锚点存在，防止页面回退成静态展示页。

## 实施顺序

先打 PostgreSQL 测试地基，再收敛后端契约，再接通模拟运行链路，最后替换前端页面和停机交互。不要先改 HTML 再补接口，否则会出现一轮无效返工。

---

### Phase 0：建立 PostgreSQL 测试基座

**文件：**
- 新建：`tests/conftest.py`
- 测试：`tests/test_dashboard_api.py`
- 测试：`tests/test_dashboard_workbench_service.py`

- [ ] **步骤 1：先写 PostgreSQL fixture**

```python
import os

import pytest
from sqlalchemy import create_engine

from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


@pytest.fixture
def pg_engine():
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(database_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def pg_store(pg_engine):
    return RuntimeStore(pg_engine)


@pytest.fixture
def test_app(pg_store):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: pg_store
    return app
```

- [ ] **步骤 2：运行一个最小测试，确认环境现在会因为缺少文件或 fixture 接线而失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py -v
```

预期：FAIL，报错类似 `file or directory not found: tests/test_dashboard_api.py`，说明 PostgreSQL 测试入口尚未补齐。

- [ ] **步骤 3：补上新增测试文件的最小骨架**

```python
from fastapi.testclient import TestClient


def test_dashboard_workbench_route_exists(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/dashboard/workbench")
    assert response.status_code == 200
```

- [ ] **步骤 4：再次运行，确认失败原因已经收敛成“路由不存在”而不是测试基座问题**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py::test_dashboard_workbench_route_exists -v
```

预期：FAIL，状态码为 `404`。

- [ ] **步骤 5：提交**

```bash
git add tests/conftest.py tests/test_dashboard_api.py
git commit -m "test: add postgresql dashboard test fixtures"
```

**阶段验收：**

- 所有新增测试统一使用 `TEST_DATABASE_URL`。
- 本计划后续步骤中不允许再出现 `sqlite:///`。
- 失败原因收敛到“业务未实现”，而不是测试底座未接通。

---

### Phase 1：收敛仪表盘读接口与真实指标

**文件：**
- 修改：`src/api/routes_dashboard.py`
- 修改：`src/storage/runtime_store.py`
- 新建：`tests/test_dashboard_api.py`
- 修改：`tests/test_bootstrap.py`

- [ ] **步骤 1：先写失败测试，锁定工作台读接口契约**

```python
from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def seed_dashboard_records(store):
    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="hash-001",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="dashboard seed",
        input_snapshot={
            "symbol": "600519.SH",
            "features": {"capital_base": 1000000, "watchlist": ["600519.SH"]},
            "market_context": {"mode": "shadow"},
        },
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        target_position_ratio=0.1,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1000.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "paper-001"},
    )
    return decision_run_id, target_position_id, execution_order_id


def test_workbench_payload_uses_runtime_store_metrics(test_app, pg_store):
    decision_run_id, target_position_id, execution_order_id = seed_dashboard_records(pg_store)
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")
    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"] == {
        "active_target_count": 1,
        "active_target_value": 100000,
        "open_orders": 1,
        "recent_decisions": 1,
    }
    assert payload["history"]["decisions"][0]["decision_run_id"] == decision_run_id
    assert payload["history"]["targets"][0]["target_position_id"] == target_position_id
    assert payload["history"]["orders"][0]["execution_order_id"] == execution_order_id
    assert "daily_pnl" not in payload["summary"]
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py::test_workbench_payload_uses_runtime_store_metrics -v
```

预期：FAIL，报错 `404` 或载荷缺少 `summary/history/orders` 字段。

- [ ] **步骤 3：编写最小实现，补齐工作台读模型**

`src/storage/runtime_store.py` 增加：

```python
def list_execution_orders(self, limit: int = 10) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(ExecutionOrderRow)
            .order_by(ExecutionOrderRow.created_at.desc())
            .limit(limit)
        ).fetchall()
        return [
            {
                "execution_order_id": row.execution_order_id,
                "target_position_id": row.target_position_id,
                "symbol": row.symbol,
                "action": row.action,
                "quantity": row.quantity,
                "limit_price": row.limit_price,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def list_broker_events(self, limit: int = 10) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(BrokerEventRow)
            .order_by(BrokerEventRow.created_at.desc())
            .limit(limit)
        ).fetchall()
        return [
            {
                "event_id": row.event_id,
                "order_id": row.order_id,
                "event_type": row.event_type,
                "payload": json.loads(row.payload_json),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def list_kill_switch_events(self, limit: int = 10) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(KillSwitchEventRow)
            .order_by(KillSwitchEventRow.created_at.desc())
            .limit(limit)
        ).fetchall()
        return [
            {
                "kill_switch_event_id": row.kill_switch_event_id,
                "active": row.active,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
```

`src/api/routes_dashboard.py` 改成单一聚合接口：

```python
@router.get("/api/v1/dashboard/workbench")
def get_dashboard_workbench(store=Depends(get_runtime_store)):
    targets = store.list_active_target_positions()
    reconciliation = store.get_reconciliation_status()
    decisions = store.list_decision_runs()[:10]
    orders = store.list_execution_orders(limit=10)
    broker_events = store.list_broker_events(limit=10)
    kill_switch_events = store.list_kill_switch_events(limit=10)

    return {
        "mode": "shadow",
        "summary": {
            "active_target_count": len(targets),
            "active_target_value": sum(item["target_value"] for item in targets),
            "open_orders": reconciliation["open_orders"],
            "recent_decisions": len(decisions),
        },
        "risk": {
            "kill_switch_active": store.get_kill_switch(),
            "healthy": reconciliation["healthy"],
        },
        "history": {
            "decisions": decisions,
            "targets": targets[:10],
            "orders": orders,
            "broker_events": broker_events,
            "kill_switch_events": kill_switch_events,
        },
    }
```

- [ ] **步骤 4：再次运行测试，并补一个路由装配检查**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py::test_workbench_payload_uses_runtime_store_metrics tests/test_bootstrap.py -v
```

预期：PASS，且 `build_app()` 暴露 `/api/v1/dashboard/workbench`。

- [ ] **步骤 5：提交**

```bash
git add src/api/routes_dashboard.py src/storage/runtime_store.py tests/test_dashboard_api.py tests/test_bootstrap.py
git commit -m "feat: add dashboard workbench read model"
```

**阶段验收：**

- `GET /api/v1/dashboard/workbench` 可返回单个聚合载荷。
- 首页摘要只包含真实可审计指标。
- `history` 至少包含 `decisions / targets / orders / broker_events / kill_switch_events` 五组数据。

---

### Phase 2：接通“运行一轮模拟交易”后端链路

**文件：**
- 新建：`src/runtime/command_service.py`
- 新建：`src/dashboard/workbench_service.py`
- 修改：`src/main.py`
- 修改：`src/api/routes_dashboard.py`
- 修改：`src/storage/runtime_store.py`
- 新建：`tests/test_dashboard_workbench_service.py`
- 修改：`tests/test_cli.py`

- [ ] **步骤 1：先写失败测试，锁定一轮模拟交易的落库结果**

```python
from src.dashboard.workbench_service import run_dashboard_simulation
from src.execution.paper_broker import PaperBroker


def test_run_dashboard_simulation_persists_full_shadow_cycle(pg_store):
    result = run_dashboard_simulation(
        payload={
            "capital_base": 1000000,
            "watchlist": ["600519.SH"],
            "manual_symbols": "300750.SZ",
            "max_position_ratio": 0.2,
            "stop_loss_ratio": 0.03,
            "daily_loss_limit_ratio": 0.05,
            "execution_mode": "full_cycle",
        },
        store=pg_store,
        quote_lookup=lambda symbol: 100.0,
        broker=PaperBroker(fill_rate=1.0),
    )

    assert result["status"] == "ok"
    assert len(result["decision_run_ids"]) == 2
    assert len(result["target_position_ids"]) == 2
    assert len(result["execution_plan_ids"]) == 2
    assert len(result["execution_order_ids"]) == 2
    assert result["timeline"][0]["stage"] == "decision"
    assert result["timeline"][-1]["stage"] == "reconcile"


def test_run_dashboard_simulation_is_blocked_by_kill_switch(pg_store):
    pg_store.insert_kill_switch_event(active=True, reason="manual halt")

    result = run_dashboard_simulation(
        payload={
            "capital_base": 1000000,
            "watchlist": ["600519.SH"],
            "manual_symbols": "",
            "max_position_ratio": 0.2,
            "stop_loss_ratio": 0.03,
            "daily_loss_limit_ratio": 0.05,
            "execution_mode": "full_cycle",
        },
        store=pg_store,
        quote_lookup=lambda symbol: 100.0,
        broker=PaperBroker(fill_rate=1.0),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "kill switch enabled"
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_workbench_service.py -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'src.dashboard.workbench_service'`。

- [ ] **步骤 3：编写最小实现，抽离命令服务并接通工作台编排**

`src/runtime/command_service.py`：

```python
from datetime import datetime, timedelta
from hashlib import sha256

from src.agents.llm_client import LLMClient
from src.decision.decision_runner import build_decision_run_record
from src.decision.input_builder import build_decision_input_snapshot
from src.portfolio.target_planner import build_target_position
from src.storage.dependencies import get_runtime_store


def run_decide_command(
    symbols: list[str],
    mock_llm: bool,
    store=None,
    decision_features: dict | None = None,
    market_context: dict | None = None,
) -> dict:
    runtime_store = store or get_runtime_store()
    if runtime_store.get_kill_switch():
        return {"status": "blocked", "reason": "kill switch enabled", "decision_run_ids": [], "target_position_ids": []}

    client = LLMClient(provider="mock")
    decision_features = decision_features or {}
    market_context = market_context or {"mode": "shadow"}
    decision_run_ids = []
    target_position_ids = []

    for symbol in symbols:
        prompt = f"Generate a shadow trading decision for {symbol}."
        input_snapshot = build_decision_input_snapshot(
            symbol=symbol,
            features=decision_features,
            market_context=market_context,
        )
        raw_output = client.generate(prompt)
        record = build_decision_run_record(
            raw=raw_output,
            symbol=symbol,
            prompt_hash=sha256(prompt.encode(\"utf-8\")).hexdigest(),
            input_snapshot=input_snapshot,
            model_name=client.model,
        )
        decision_run_id = runtime_store.insert_decision_run(**record)
        decision_run_ids.append(decision_run_id)

        if record["parsed_action"] in {"BUY", "SELL"} and record["target_position_ratio"] > 0:
            target = build_target_position(
                symbol=symbol,
                action=record["parsed_action"],
                target_position_ratio=min(record["target_position_ratio"], decision_features.get("max_position_ratio", 1.0)),
                net_asset_value=decision_features["capital_base"],
                expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
            )
            target_position_ids.append(
                runtime_store.insert_target_position(
                    decision_run_id=decision_run_id,
                    symbol=target["symbol"],
                    action=target["action"],
                    target_value=target["target_value"],
                    target_position_ratio=target["target_position_ratio"],
                    expires_at=target["expires_at"],
                )
            )

    return {"status": "ok", "decision_run_ids": decision_run_ids, "target_position_ids": target_position_ids}
```

`src/dashboard/workbench_service.py`：

```python
from src.execution.execution_plan_service import build_execution_plan
from src.execution.paper_broker import PaperBroker
from src.runtime.command_service import run_decide_command


def normalize_symbols(watchlist: list[str], manual_symbols: str) -> list[str]:
    manual = [item.strip().upper() for item in manual_symbols.split(",") if item.strip()]
    merged = [item.strip().upper() for item in watchlist if item.strip()] + manual
    return list(dict.fromkeys(merged))


def run_dashboard_simulation(payload: dict, store, quote_lookup, broker: PaperBroker) -> dict:
    symbols = normalize_symbols(payload["watchlist"], payload["manual_symbols"])
    summary = run_decide_command(
        symbols=symbols,
        mock_llm=True,
        store=store,
        decision_features={
            "capital_base": payload["capital_base"],
            "watchlist": payload["watchlist"],
            "manual_symbols": payload["manual_symbols"],
            "max_position_ratio": payload["max_position_ratio"],
            "stop_loss_ratio": payload["stop_loss_ratio"],
            "daily_loss_limit_ratio": payload["daily_loss_limit_ratio"],
        },
        market_context={"mode": "shadow", "execution_mode": payload["execution_mode"]},
    )
    if summary["status"] != "ok":
        return summary

    execution_plan_ids = []
    execution_order_ids = []
    timeline = [{"stage": "decision", "decision_run_ids": summary["decision_run_ids"]}]

    targets = store.list_target_positions_by_ids(summary["target_position_ids"])
    for target in targets:
        plan = build_execution_plan(target, {"approved": True, "reason": "shadow workbench"})
        plan_id = store.insert_execution_plan(
            symbol=plan["symbol"],
            action=plan["action"],
            target_value=plan["target_value"],
            reason=plan["reason"],
        )
        execution_plan_ids.append(plan_id)

        if payload["execution_mode"] != "full_cycle":
            continue

        reference_price = quote_lookup(target["symbol"])
        quantity = max(100, int(target["target_value"] / reference_price / 100) * 100)
        execution_order_id = store.insert_execution_order(
            target_position_id=target["target_position_id"],
            symbol=target["symbol"],
            action=target["action"],
            quantity=quantity,
            limit_price=reference_price,
        )
        execution_order_ids.append(execution_order_id)
        accepted = broker.submit_order({"order_id": execution_order_id, "symbol": target["symbol"], "quantity": quantity})
        store.insert_broker_order_event(
            execution_order_id=execution_order_id,
            event_id=f"{execution_order_id}-submitted",
            event_type="SUBMITTED",
            payload=accepted,
        )
        fill_event = broker.simulate_fill(execution_order_id)
        store.insert_broker_order_event(
            execution_order_id=execution_order_id,
            event_id=fill_event["event_id"],
            event_type=fill_event["event_type"],
            payload=fill_event,
        )

    timeline.append({"stage": "execution_plan", "execution_plan_ids": execution_plan_ids})
    if payload["execution_mode"] == "full_cycle":
        timeline.append({"stage": "execution_order", "execution_order_ids": execution_order_ids})
    timeline.append({"stage": "reconcile", "status": store.get_reconciliation_status()})

    return {
        "status": "ok",
        "decision_run_ids": summary["decision_run_ids"],
        "target_position_ids": summary["target_position_ids"],
        "execution_plan_ids": execution_plan_ids,
        "execution_order_ids": execution_order_ids,
        "timeline": timeline,
    }
```

`src/storage/runtime_store.py` 同时增加按 ID 读取目标仓位，避免把旧运行的活跃目标混入本轮执行：

```python
def list_target_positions_by_ids(self, target_position_ids: list[str]) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(TargetPositionRow)
            .where(TargetPositionRow.target_position_id.in_(target_position_ids))
            .order_by(TargetPositionRow.created_at.asc())
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
```

`src/main.py` 改成导入而不是自持实现：

```python
from src.runtime.command_service import run_decide_command, run_halt_command
```

`src/api/routes_dashboard.py` 增加写接口：

```python
@router.post("/api/v1/dashboard/simulations")
def run_dashboard_workbench(payload: dict, store=Depends(get_runtime_store)):
    broker = PaperBroker(fill_rate=1.0)
    return run_dashboard_simulation(
        payload=payload,
        store=store,
        quote_lookup=lambda symbol: 100.0,
        broker=broker,
    )
```

- [ ] **步骤 4：再次运行测试，并补一个 HTTP 层测试**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_workbench_service.py tests/test_cli.py -v
```

预期：PASS，且 `tests/test_cli.py` 仍然验证 `decide`、`halt` 命令行为未回退。

- [ ] **步骤 5：提交**

```bash
git add src/runtime/command_service.py src/dashboard/workbench_service.py src/main.py src/api/routes_dashboard.py src/storage/runtime_store.py tests/test_dashboard_workbench_service.py tests/test_cli.py
git commit -m "feat: connect dashboard shadow simulation workflow"
```

**阶段验收：**

- 页面后端可以接收一份模拟配置并写入现有主链表。
- 单次运行至少落下 `decision_run / target_position / execution_plan`。
- 在 `execution_mode=full_cycle` 时，还必须落下 `execution_order / broker_event / reconcile`。
- `kill switch` 打开时，运行接口必须返回 `blocked`，不能静默继续。

---

### Phase 3：替换静态首页为三栏工作台

**文件：**
- 修改：`src/api/dashboard.html`
- 新建：`tests/test_dashboard_html.py`
- 修改：`tests/test_dashboard_api.py`

- [ ] **步骤 1：先写失败测试，锁定首屏结构**

```python
from fastapi.testclient import TestClient


def test_dashboard_page_contains_workbench_regions(test_app):
    client = TestClient(test_app)
    response = client.get("/dashboard")
    html = response.text

    assert response.status_code == 200
    assert 'id="simulation-form"' in html
    assert 'id="run-simulation-button"' in html
    assert 'id="timeline-panel"' in html
    assert 'id="risk-panel"' in html
    assert 'id="history-tabs"' in html
    assert 'id="daily-pnl"' not in html
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_html.py::test_dashboard_page_contains_workbench_regions -v
```

预期：FAIL，找不到 `simulation-form`、`timeline-panel` 等 DOM 锚点。

- [ ] **步骤 3：编写最小实现，完成三栏工作台与前端交互**

`src/api/dashboard.html` 至少要包含以下骨架：

```html
<main class="workbench-layout">
  <section class="panel panel-config">
    <form id="simulation-form">
      <label>模拟总资金 <input id="capital-base" name="capital_base" type="number" value="1000000" /></label>
      <label>观察列表 <textarea id="watchlist" name="watchlist">600519.SH</textarea></label>
      <label>手动股票代码 <input id="manual-symbols" name="manual_symbols" type="text" placeholder="300750.SZ, 000001.SZ" /></label>
      <label>单票最大仓位 <input id="max-position-ratio" name="max_position_ratio" type="number" step="0.01" value="0.20" /></label>
      <label>止损阈值 <input id="stop-loss-ratio" name="stop_loss_ratio" type="number" step="0.01" value="0.03" /></label>
      <label>单日亏损阈值 <input id="daily-loss-limit-ratio" name="daily_loss_limit_ratio" type="number" step="0.01" value="0.05" /></label>
      <label>执行方式
        <select id="execution-mode" name="execution_mode">
          <option value="full_cycle" selected>完整链路执行</option>
          <option value="decide_only">仅生成决策</option>
        </select>
      </label>
      <button id="run-simulation-button" type="submit">运行一轮模拟交易</button>
    </form>
  </section>

  <section class="panel panel-timeline" id="timeline-panel"></section>

  <section class="panel panel-risk" id="risk-panel">
    <button id="kill-switch-toggle" type="button">停止交易</button>
    <div id="risk-summary"></div>
  </section>
</main>

<section class="panel panel-history" id="history-tabs">
  <button data-tab="decisions">最近决策</button>
  <button data-tab="orders">最近订单</button>
  <button data-tab="targets">目标仓位</button>
  <button data-tab="events">异常与停机</button>
  <div id="history-content"></div>
</section>
```

配套脚本至少包括：

```javascript
async function loadWorkbench() {
  const response = await fetch('/api/v1/dashboard/workbench');
  const payload = await response.json();
  renderSummary(payload.summary, payload.risk);
  renderTimeline(payload.latest_run || {decisions: [], orders: [], broker_events: [], reconciliation: {open_orders: 0, healthy: true}});
  renderHistory(payload.history);
}

async function submitSimulation(event) {
  event.preventDefault();
  const payload = {
    capital_base: Number(document.getElementById('capital-base').value),
    watchlist: document.getElementById('watchlist').value.split('\n').map(v => v.trim()).filter(Boolean),
    manual_symbols: document.getElementById('manual-symbols').value,
    max_position_ratio: Number(document.getElementById('max-position-ratio').value),
    stop_loss_ratio: Number(document.getElementById('stop-loss-ratio').value),
    daily_loss_limit_ratio: Number(document.getElementById('daily-loss-limit-ratio').value),
    execution_mode: document.getElementById('execution-mode').value,
  };
  await fetch('/api/v1/dashboard/simulations', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  await loadWorkbench();
}

document.getElementById('simulation-form').addEventListener('submit', submitSimulation);
loadWorkbench();
setInterval(loadWorkbench, 30000);
```

- [ ] **步骤 4：再次运行测试，并确认页面不再依赖假卡片**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_html.py tests/test_dashboard_api.py::test_workbench_payload_uses_runtime_store_metrics -v
```

预期：PASS，且页面 HTML 不再包含旧的 `daily-pnl` DOM。

- [ ] **步骤 5：提交**

```bash
git add src/api/dashboard.html tests/test_dashboard_html.py tests/test_dashboard_api.py
git commit -m "feat: replace static dashboard with trading workbench"
```

**阶段验收：**

- 首屏必须有“配置区 + 主按钮 + 时间线区 + 风控区 + 历史区”。
- 首页不再显示任何硬编码样例行。
- 用户进入页面后无需 CLI，就能看懂下一步操作。

---

### Phase 4：统一停机链路与右侧风控面板

**文件：**
- 修改：`src/api/routes_kill_switch.py`
- 修改：`src/api/routes_dashboard.py`
- 修改：`src/api/dashboard.html`
- 修改：`tests/test_dashboard_api.py`
- 修改：`tests/test_kill_switch_pg.py`

- [ ] **步骤 1：先写失败测试，锁定页面停机行为**

```python
from fastapi.testclient import TestClient


def test_kill_switch_activate_records_event_and_updates_workbench(test_app):
    client = TestClient(test_app)

    activate = client.post("/api/v1/kill-switch/activate", json={"reason": "dashboard manual halt"})
    assert activate.status_code == 200

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["risk"]["kill_switch_active"] is True
    assert payload["history"]["kill_switch_events"][0]["reason"] == "dashboard manual halt"


def test_kill_switch_deactivate_records_resume_event(test_app):
    client = TestClient(test_app)
    client.post("/api/v1/kill-switch/activate", json={"reason": "dashboard manual halt"})

    deactivate = client.post("/api/v1/kill-switch/deactivate", json={"reason": "dashboard manual resume"})
    assert deactivate.status_code == 200

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["risk"]["kill_switch_active"] is False
    assert payload["history"]["kill_switch_events"][0]["reason"] == "dashboard manual resume"
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py::test_kill_switch_activate_records_event_and_updates_workbench tests/test_dashboard_api.py::test_kill_switch_deactivate_records_resume_event -v
```

预期：FAIL，因为当前接口只改 `kill_switch_state`，不会写 `kill_switch_event`。

- [ ] **步骤 3：编写最小实现，统一页面与后端的停机语义**

`src/api/routes_kill_switch.py` 改成事件驱动写法：

```python
from fastapi import APIRouter, Body, Depends


@router.post("/kill-switch/activate")
def activate_kill_switch(payload: dict = Body(default={"reason": "manual activate"}), store=Depends(get_runtime_store)) -> dict:
    reason = payload.get("reason", "manual activate")
    store.insert_kill_switch_event(active=True, reason=reason)
    return {"activated": True, "reason": reason}


@router.post("/kill-switch/deactivate")
def deactivate_kill_switch(payload: dict = Body(default={"reason": "manual deactivate"}), store=Depends(get_runtime_store)) -> dict:
    reason = payload.get("reason", "manual deactivate")
    store.insert_kill_switch_event(active=False, reason=reason)
    return {"deactivated": True, "reason": reason}
```

`src/api/dashboard.html` 的右栏按钮改成读 `risk.kill_switch_active` 并切换：

```javascript
async function toggleKillSwitch(active) {
  const path = active ? '/api/v1/kill-switch/deactivate' : '/api/v1/kill-switch/activate';
  const reason = active ? 'dashboard manual resume' : 'dashboard manual halt';
  await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reason}),
  });
  await loadWorkbench();
}
```

- [ ] **步骤 4：再次运行测试，并补 store 级回归**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py tests/test_kill_switch_pg.py -v
```

预期：PASS，页面和 store 看到的是同一套停机状态与事件历史。

- [ ] **步骤 5：提交**

```bash
git add src/api/routes_kill_switch.py src/api/routes_dashboard.py src/api/dashboard.html tests/test_dashboard_api.py tests/test_kill_switch_pg.py
git commit -m "feat: unify dashboard kill switch flow"
```

**阶段验收：**

- 页面停机按钮只能走现有 `kill-switch` API，不能自造第二条停机路径。
- 每一次停机和恢复都必须写事件历史。
- 停机后页面主按钮应表现为“阻断执行而不是假提交成功”。

---

### Phase 5：联调、历史回放与最终验收

**文件：**
- 修改：`src/api/routes_dashboard.py`
- 修改：`tests/test_dashboard_api.py`
- 修改：`tests/test_bootstrap.py`
- 修改：`docs/superpowers/plans/2026-05-24-a-share-hub-phase-acceptance.md`

- [ ] **步骤 1：先写失败测试，锁定完整工作台回放**

```python
from fastapi.testclient import TestClient


def test_workbench_reflects_latest_simulation_run(test_app):
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/dashboard/simulations",
        json={
            "capital_base": 1000000,
            "watchlist": ["600519.SH"],
            "manual_symbols": "300750.SZ",
            "max_position_ratio": 0.2,
            "stop_loss_ratio": 0.03,
            "daily_loss_limit_ratio": 0.05,
            "execution_mode": "full_cycle",
        },
    )
    assert response.status_code == 200

    workbench = client.get("/api/v1/dashboard/workbench").json()
    assert workbench["summary"]["recent_decisions"] >= 1
    assert len(workbench["history"]["decisions"]) >= 1
    assert len(workbench["history"]["orders"]) >= 1
    assert workbench["risk"]["healthy"] is True
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py::test_workbench_reflects_latest_simulation_run -v
```

预期：FAIL，原因通常是 `workbench` 尚未返回最新运行时间线或历史集未刷新。

- [ ] **步骤 3：编写最小实现，补齐最新运行摘要与验收文档**

`src/api/routes_dashboard.py` 返回 `latest_run`：

```python
return {
    "mode": "shadow",
    "summary": {
        "active_target_count": len(targets),
        "active_target_value": sum(item["target_value"] for item in targets),
        "open_orders": reconciliation["open_orders"],
        "recent_decisions": len(decisions),
    },
    "risk": {
        "kill_switch_active": store.get_kill_switch(),
        "healthy": reconciliation["healthy"],
    },
    "latest_run": {
        "decisions": decisions[:3],
        "orders": orders[:3],
        "broker_events": broker_events[:3],
        "reconciliation": reconciliation,
    },
    "history": {
        "decisions": decisions,
        "targets": targets[:10],
        "orders": orders,
        "broker_events": broker_events,
        "kill_switch_events": kill_switch_events,
    },
}
```

同时把 `[docs/superpowers/plans/2026-05-24-a-share-hub-phase-acceptance.md](/Users/shenmingjie/workSpace/tranding/a-share-hub/docs/superpowers/plans/2026-05-24-a-share-hub-phase-acceptance.md)` 中与仪表盘相关的 Phase 说明同步成下面的验收命令：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py tests/test_dashboard_workbench_service.py tests/test_dashboard_html.py tests/test_kill_switch_pg.py tests/test_bootstrap.py -v
```

- [ ] **步骤 4：运行完整验收，并做一次手工联调**

运行：

```bash
TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test pytest tests/test_dashboard_api.py tests/test_dashboard_workbench_service.py tests/test_dashboard_html.py tests/test_kill_switch_pg.py tests/test_bootstrap.py -v
```

然后手工联调：

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8010
```

浏览器验收步骤：

1. 打开 `http://127.0.0.1:8010/dashboard`
2. 在左栏填写 `600519.SH` 和 `300750.SZ`
3. 点击“运行一轮模拟交易”
4. 确认中央时间线出现 `decision -> execution_plan -> execution_order -> reconcile`
5. 点击右栏停机按钮
6. 再次点击主按钮，确认页面提示已阻断
7. 点击恢复按钮，确认可再次运行

预期：自动化测试全部通过，手工流程无假数据和死按钮。

- [ ] **步骤 5：提交**

```bash
git add src/api/routes_dashboard.py tests/test_dashboard_api.py tests/test_dashboard_workbench_service.py tests/test_dashboard_html.py tests/test_kill_switch_pg.py tests/test_bootstrap.py docs/superpowers/plans/2026-05-24-a-share-hub-phase-acceptance.md
git commit -m "docs: finalize dashboard workbench acceptance plan"
```

**阶段验收：**

- 页面已经从“静态展示页”变成“可执行工作台”。
- 自动化测试覆盖读接口、写接口、页面骨架、停机流和路由装配。
- 手工联调能完整跑通一轮模拟交易，并能在页面内完成停机与恢复。

---

## 最终验收标准

- `GET /dashboard` 返回的页面包含明确的首屏操作入口，而不是纯展示卡片。
- `GET /api/v1/dashboard/workbench` 返回单一聚合数据结构，前端不再拼接多套不一致契约。
- `POST /api/v1/dashboard/simulations` 能在 PostgreSQL 中落下完整模拟交易链路记录。
- `POST /api/v1/kill-switch/activate` 与 `POST /api/v1/kill-switch/deactivate` 都会写事件历史。
- 所有本计划新增/修改测试都使用 PostgreSQL，不能回退到 SQLite。

## 风险与边界

- 当前仓库没有真实持仓账本，因此不要在实现中重新引入“总资产 / 今日盈亏”这类假指标。
- 当前仓库没有页面级认证，本计划默认本地内网环境使用，不新增登录系统。
- `quote_lookup=lambda symbol: 100.0` 只适用于最小可运行版本。若下一轮要接真行情，应单独立项接 `MarketSnapshotService`，不要在本计划里半接半不接。
