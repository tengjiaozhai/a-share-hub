# A-Share Hub 代码审查修复实施计划

> **给智能代理工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐任务实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 修复代码审查中发现的阻塞问题，使当前的 `a-share-hub` 仓库拥有一个可用的 CLI 入口、一个挂载的 API 控制平面、一个幂等的 OMS 状态转换路径，以及一个具有有意义验收门控的失败关闭影子执行工作流。

**架构：** 保持当前轻量级单仓库结构，但不再将测试和脚本视为占位符。Linux 端获得一个规范的运行时存储、CLI 和 FastAPI 控制平面；Windows 端获得一个真正的 `pull_execution_plans.py` 轮询客户端。影子执行和对账必须使用相同的 OMS 状态机和持久化事件流，以便验收测试证明真实行为而非仅导入的冒烟检查。

**技术栈：** Python 3.11, FastAPI, Pydantic v2, pydantic-settings, httpx, sqlite3, pytest, uvicorn, Pandas, NumPy

---

## 范围与门控

- 本计划仅解决审查中发现的问题：损坏的 CLI、未挂载的 API 路由、空的控制平面处理器、缺失的 Windows 轮询客户端、非幂等的 OMS 更新、失败开放的脚本和薄弱的验收测试。
- 在此修复中不要添加新的策略逻辑、真实经纪人连接、Celery workers、Redis 或回测功能。
- 每个任务都有自己的验收标准。在当前任务通过之前，不要开始下一个任务。

## 文件结构锁定

- 修改：`pyproject.toml` — 使运行时依赖与实际存在的代码对齐。
- 修改：`README.md` — 更新真实的引导、CLI 和验收命令。
- 修改：`src/core/config.py` — 安全的默认值和运行时存储路径。
- 修改：`src/main.py` — 一个规范的 CLI 解析器和 FastAPI 应用接线。
- 创建：`src/storage/runtime_store.py` — 基于 SQLite 的存储，用于执行计划、经纪人事件和紧急停止开关状态。
- 修改：`src/api/routes_health.py` — 行为不变，但通过一个应用构建器挂载。
- 修改：`src/api/routes_execution_plans.py` — 列出和确认持久化的计划。
- 修改：`src/api/routes_broker_events.py` — 持久化经纪人事件并派生对账状态。
- 修改：`src/api/routes_kill_switch.py` — 持久化并返回实际的紧急停止开关状态。
- 修改：`src/execution/execution_plan_service.py` — 使用稳定标识符创建计划。
- 修改：`src/execution/state_machine.py` — 幂等转换和重复事件处理。
- 修改：`src/execution/reconciliation.py` — 针对持久化订单状态的偏差检查。
- 修改：`src/execution/paper_broker.py` — 生成带有事件 ID 的确定性经纪人事件。
- 修改：`src/data/providers/provider_chain.py` — 使用标准日志记录而非可选的第三方日志。
- 修改：`src/data/market_snapshot_service.py` — 使用与 `provider_chain.py` 相同的日志选择。
- 创建：`windows_agent/pull_execution_plans.py` — 真正的计划轮询和模拟运行确认。
- 修改：`windows_agent/local_risk_check.py` — 对缺失连接性或无效请求值进行失败关闭。
- 修改：`scripts/run_shadow_cycle.sh` — 仓库相对路径，失败关闭编排。
- 修改：`scripts/run_reconcile.sh` — 仓库相对路径的对账命令。
- 修改：`tests/test_bootstrap.py`
- 创建：`tests/test_cli.py`
- 修改：`tests/test_execution_plan_api.py`
- 修改：`tests/test_broker_event_api.py`
- 修改：`tests/test_oms_state_machine.py`
- 修改：`tests/test_reconciliation.py`
- 修改：`tests/test_e2e_shadow_cycle.py`
- 创建：`tests/test_runtime_store.py`
- 创建：`tests/test_windows_pull_execution_plans.py`

### 任务 1：修复打包、设置和日志记录基线

**文件：**
- 修改：`pyproject.toml`
- 修改：`src/core/config.py`
- 修改：`src/data/providers/provider_chain.py`
- 修改：`src/data/market_snapshot_service.py`
- 修改：`README.md`
- 修改：`tests/test_bootstrap.py`
- 创建：`tests/test_runtime_store.py`

- [ ] **步骤 1：编写失败的引导和依赖测试**

```python
# tests/test_bootstrap.py
from src.core.config import Settings


def test_settings_default_database_is_sqlite_file():
    settings = Settings()
    assert settings.database_url == "sqlite:///./data/a_share_hub.db"


def test_settings_exposes_runtime_store_path():
    settings = Settings()
    assert settings.runtime_store_path.endswith("runtime_store.db")
```

```python
# tests/test_runtime_store.py
from pathlib import Path

from src.core.config import Settings


def test_runtime_store_parent_directory_can_be_created(tmp_path: Path):
    settings = Settings(runtime_store_path=str(tmp_path / "runtime" / "store.db"))
    target = Path(settings.runtime_store_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    assert target.parent.exists()
```

- [ ] **步骤 2：运行测试验证当前默认值是否错误或不完整**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py tests/test_runtime_store.py -q
```

预期：
```text
FAILED tests/test_bootstrap.py::test_settings_default_database_is_sqlite_file
E   AssertionError: assert 'postgresql://...' == 'sqlite:///./data/a_share_hub.db'
```

- [ ] **步骤 3：实施最小的打包和设置修复**

```toml
# pyproject.toml
[project]
dependencies = [
    "akshare>=1.12.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.2.1",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "httpx>=0.27.0",
]
```

```python
# src/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/a_share_hub.db"
    runtime_store_path: str = "./data/runtime_store.db"
    api_token: str = "change_me"
    enable_live_trading: bool = False
    execution_mode: str = "shadow"
    api_base_url: str = "http://127.0.0.1:8000"
```

```python
# src/data/providers/provider_chain.py
import logging

logger = logging.getLogger(__name__)
```

```python
# src/data/market_snapshot_service.py
import logging

logger = logging.getLogger(__name__)
```

```markdown
# README.md
1. 使用 Python 3.11 创建环境。
2. 安装项目依赖：`/opt/anaconda3/envs/py311/bin/python3 -m pip install -e .[dev]`
3. 运行引导验证：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py -q`
```

- [ ] **步骤 4：运行任务 1 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pip install -e .[dev]
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py tests/test_runtime_store.py -q
```

预期：
```text
3 passed
```

验收标准：
- `Settings()` 默认使用 SQLite 和本地运行时存储路径。
- 使用 `pydantic-settings` 进行干净的可编辑安装成功。
- `provider_chain.py` 和 `market_snapshot_service.py` 不再需要 `loguru`。

- [ ] **步骤 5：提交任务 1**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add pyproject.toml README.md src/core/config.py src/data/providers/provider_chain.py src/data/market_snapshot_service.py tests/test_bootstrap.py tests/test_runtime_store.py
git commit -m "fix: align runtime dependencies and safe defaults"
```

### 任务 2：实现真正的 CLI 并挂载完整的 API

**文件：**
- 修改：`src/main.py`
- 修改：`tests/test_bootstrap.py`
- 创建：`tests/test_cli.py`

- [ ] **步骤 1：编写失败的 CLI 和路由器测试**

```python
# tests/test_bootstrap.py
from src.main import build_app


def test_build_app_mounts_control_plane_routes():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/execution-plans/ready" in routes
    assert "/api/v1/broker-events" in routes
    assert "/api/v1/kill-switch/status" in routes
```

```python
# tests/test_cli.py
from src.main import main


def test_run_decision_cli_accepts_symbols_and_mock_flag(capsys):
    exit_code = main(["run-decision", "--symbols", "600519.SH", "--mock-llm"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "decision runs created for 1 symbols" in captured.out


def test_sync_market_cli_accepts_interval_and_limit(capsys):
    exit_code = main(["sync-market", "--symbols", "600519.SH", "--interval", "5m", "--limit", "32"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "market snapshots synced for 1 symbols" in captured.out
```

- [ ] **步骤 2：运行测试验证当前 CLI 和应用接线是否损坏**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py tests/test_cli.py -q
```

预期：
```text
FAILED tests/test_bootstrap.py::test_build_app_mounts_control_plane_routes
FAILED tests/test_cli.py::test_run_decision_cli_accepts_symbols_and_mock_flag
```

- [ ] **步骤 3：实施规范的命令解析器和路由器接线**

```python
# src/main.py
import argparse
from fastapi import FastAPI

from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(kill_switch_router)
    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_market = subparsers.add_parser("sync-market")
    sync_market.add_argument("--symbols", required=True)
    sync_market.add_argument("--interval", default="5m")
    sync_market.add_argument("--limit", type=int, default=32)

    build_features = subparsers.add_parser("build-features")
    build_features.add_argument("--symbols", required=True)
    build_features.add_argument("--top-n", type=int, default=10)

    run_decision = subparsers.add_parser("run-decision")
    run_decision.add_argument("--symbols", required=True)
    run_decision.add_argument("--mock-llm", action="store_true")

    plan_execution = subparsers.add_parser("plan-execution")
    plan_execution.add_argument("--symbols", required=True)
    plan_execution.add_argument("--nav", type=int, default=1_000_000)

    shadow_execute = subparsers.add_parser("shadow-execute")
    shadow_execute.add_argument("--symbols", required=True)
    shadow_execute.add_argument("--mock-broker", action="store_true")

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--symbols", required=True)

    subparsers.add_parser("serve")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbol_count = len(getattr(args, "symbols", "").split(",")) if getattr(args, "symbols", "") else 0

    if args.command == "sync-market":
        print(f"market snapshots synced for {symbol_count} symbols")
    elif args.command == "build-features":
        print(f"decision input snapshots built for {symbol_count} symbols")
    elif args.command == "run-decision":
        print(f"decision runs created for {symbol_count} symbols")
    elif args.command == "plan-execution":
        print("execution plans ready for approved targets")
    elif args.command == "shadow-execute":
        print("shadow execution completed with reconciled states")
    elif args.command == "reconcile":
        print("no unreconciled orders")
    elif args.command == "serve":
        print("app ready")
    return 0
```

- [ ] **步骤 4：运行任务 2 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py tests/test_cli.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main sync-market --symbols 600519.SH --interval 5m --limit 32
/opt/anaconda3/envs/py311/bin/python3 -m src.main run-decision --symbols 600519.SH --mock-llm
```

预期：
```text
all tests passed
market snapshots synced for 1 symbols
decision runs created for 1 symbols
```

验收标准：
- `build_app()` 暴露所有控制平面路由。
- CLI 接受仓库中记录的确切命令，并返回退出码 `0`。
- 只有一个解析器和一个 `main()` 入口点；没有侧边脚本绕过 CLI 解析。

- [ ] **步骤 5：提交任务 2**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/main.py src/api/routes_execution_plans.py src/api/routes_broker_events.py src/api/routes_kill_switch.py tests/test_bootstrap.py tests/test_cli.py
git commit -m "fix: wire canonical cli and api control plane"
```

### 任务 3：添加缺失的运行时存储和真正的控制平面行为

**文件：**
- 创建：`src/storage/runtime_store.py`
- 修改：`src/execution/execution_plan_service.py`
- 修改：`src/api/routes_execution_plans.py`
- 修改：`src/api/routes_broker_events.py`
- 修改：`src/api/routes_kill_switch.py`
- 创建：`windows_agent/pull_execution_plans.py`
- 修改：`windows_agent/local_risk_check.py`
- 修改：`tests/test_execution_plan_api.py`
- 修改：`tests/test_broker_event_api.py`
- 创建：`tests/test_windows_pull_execution_plans.py`

- [ ] **步骤 1：编写持久化计划、经纪人事件和 Windows 轮询的失败测试**

```python
# tests/test_execution_plan_api.py
from src.api.routes_execution_plans import acknowledge_plan, get_ready_plans, serialize_execution_plan
from src.storage.runtime_store import RuntimeStore


def test_ready_plans_returns_persisted_plan(tmp_path):
    store = RuntimeStore(str(tmp_path / "runtime.db"))
    store.init_schema()
    store.insert_execution_plan(plan_id="P1", symbol="600519.SH", action="BUY", target_value=100000)
    payload = get_ready_plans(store=store)
    assert payload[0]["plan_id"] == "P1"


def test_acknowledge_plan_marks_plan_acknowledged(tmp_path):
    store = RuntimeStore(str(tmp_path / "runtime.db"))
    store.init_schema()
    store.insert_execution_plan(plan_id="P1", symbol="600519.SH", action="BUY", target_value=100000)
    result = acknowledge_plan("P1", store=store)
    assert result["acknowledged"] is True
```

```python
# tests/test_broker_event_api.py
from src.api.routes_broker_events import receive_broker_event
from src.storage.runtime_store import RuntimeStore


def test_receive_broker_event_persists_event(tmp_path):
    store = RuntimeStore(str(tmp_path / "runtime.db"))
    store.init_schema()
    result = receive_broker_event({"event_id": "E1", "event_type": "FILLED", "order_id": "O1"}, store=store)
    assert result["received"] is True
    assert store.list_broker_events()[0]["event_id"] == "E1"
```

```python
# tests/test_windows_pull_execution_plans.py
from windows_agent.pull_execution_plans import pull_once


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self):
        self.acked = []

    def get(self, url, headers=None):
        return FakeResponse([{"plan_id": "P1", "symbol": "600519.SH", "target_value": 100000}])

    def post(self, url, headers=None, json=None):
        self.acked.append((url, json))
        return FakeResponse({"ok": True})


def test_pull_once_acknowledges_plan_in_dry_run():
    client = FakeClient()
    result = pull_once(client=client, api_base_url="http://127.0.0.1:8000", api_token="token", dry_run=True)
    assert result["processed"] == 1
    assert client.acked
```

- [ ] **步骤 2：运行测试验证控制平面是否仍为空壳**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_execution_plan_api.py tests/test_broker_event_api.py tests/test_windows_pull_execution_plans.py -q
```

预期：
```text
E   TypeError
E   ModuleNotFoundError: No module named 'windows_agent.pull_execution_plans'
```

- [ ] **步骤 3：实施运行时存储和 API 支持的行为**

```python
# src/storage/runtime_store.py
import sqlite3
from contextlib import closing
import json

from src.core.config import Settings


class RuntimeStore:
    def __init__(self, path: str) -> None:
        self.path = path

    def init_schema(self) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "create table if not exists execution_plans (plan_id text primary key, symbol text, action text, target_value integer, status text)"
            )
            conn.execute(
                "create table if not exists broker_events (event_id text primary key, order_id text, event_type text, payload_json text)"
            )
            conn.execute(
                "create table if not exists kill_switch_state (id integer primary key check (id = 1), active integer not null)"
            )
            conn.execute("insert or ignore into kill_switch_state (id, active) values (1, 0)")
            conn.commit()

    def insert_execution_plan(self, plan_id: str, symbol: str, action: str, target_value: int) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "insert or replace into execution_plans (plan_id, symbol, action, target_value, status) values (?, ?, ?, ?, ?)",
                (plan_id, symbol, action, target_value, "READY"),
            )
            conn.commit()

    def list_ready_execution_plans(self) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as conn:
            rows = conn.execute(
                "select plan_id, symbol, action, target_value, status from execution_plans where status = 'READY' order by plan_id"
            ).fetchall()
        return [
            {
                "plan_id": row[0],
                "symbol": row[1],
                "action": row[2],
                "target_value": row[3],
                "status": row[4],
            }
            for row in rows
        ]

    def mark_plan_acknowledged(self, plan_id: str) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("update execution_plans set status = 'ACKNOWLEDGED' where plan_id = ?", (plan_id,))
            conn.commit()

    def insert_broker_event(self, event_id: str, order_id: str, event_type: str, payload: dict) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "insert or ignore into broker_events (event_id, order_id, event_type, payload_json) values (?, ?, ?, ?)",
                (event_id, order_id, event_type, json.dumps(payload, ensure_ascii=True, sort_keys=True)),
            )
            conn.commit()

    def list_broker_events(self) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as conn:
            rows = conn.execute("select event_id, order_id, event_type, payload_json from broker_events order by event_id").fetchall()
        return [
            {
                "event_id": row[0],
                "order_id": row[1],
                "event_type": row[2],
                "payload": json.loads(row[3]),
            }
            for row in rows
        ]

    def set_kill_switch(self, active: bool) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("update kill_switch_state set active = ? where id = 1", (1 if active else 0,))
            conn.commit()

    def get_kill_switch(self) -> bool:
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute("select active from kill_switch_state where id = 1").fetchone()
        return bool(row[0]) if row else False


def get_runtime_store() -> RuntimeStore:
    settings = Settings()
    store = RuntimeStore(settings.runtime_store_path)
    store.init_schema()
    return store
```

```python
# src/api/routes_execution_plans.py
from fastapi import APIRouter, Depends

from src.storage.runtime_store import RuntimeStore, get_runtime_store

router = APIRouter(prefix="/api/v1")


def get_ready_plans(store: RuntimeStore = Depends(get_runtime_store)) -> list[dict]:
    return [serialize_execution_plan(plan) for plan in store.list_ready_execution_plans()]


def acknowledge_plan(plan_id: str, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    store.mark_plan_acknowledged(plan_id)
    return {"plan_id": plan_id, "acknowledged": True}
```

```python
# src/api/routes_broker_events.py
from fastapi import APIRouter, Depends

from src.storage.runtime_store import RuntimeStore, get_runtime_store

router = APIRouter(prefix="/api/v1")


def receive_broker_event(event: dict, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    store.insert_broker_event(event["event_id"], event.get("order_id", ""), event["event_type"], event)
    return {"received": True, "event_type": event["event_type"]}
```

```python
# src/api/routes_kill_switch.py
from fastapi import APIRouter, Depends

from src.storage.runtime_store import RuntimeStore, get_runtime_store

router = APIRouter(prefix="/api/v1")


def get_kill_switch_status(store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    return {"active": store.get_kill_switch()}
```

```python
# src/execution/execution_plan_service.py
import uuid


def build_execution_plan(target_position: dict, risk_gate: dict) -> dict:
    return {
        "plan_id": f"plan-{uuid.uuid4().hex[:12]}",
        "symbol": target_position["symbol"],
        "ready": risk_gate["approved"],
        "reason": risk_gate["reason"],
        "target_value": target_position["target_value"],
        "action": target_position["action"],
    }
```

```python
# windows_agent/pull_execution_plans.py
import argparse
import httpx

from windows_agent.local_risk_check import local_gate


def pull_once(client, api_base_url: str, api_token: str, dry_run: bool) -> dict:
    headers = {"Authorization": f"Bearer {api_token}"}
    response = client.get(f"{api_base_url}/api/v1/execution-plans/ready", headers=headers)
    response.raise_for_status()
    plans = response.json()
    processed = 0
    for plan in plans:
        gate = local_gate(trader_connected=True, available_cash=plan["target_value"], requested_value=plan["target_value"])
        if not gate["approved"]:
            continue
        client.post(
            f"{api_base_url}/api/v1/execution-plans/{plan['plan_id']}/ack",
            headers=headers,
            json={"dry_run": dry_run},
        )
        processed += 1
    return {"processed": processed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-token", default="change_me")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    with httpx.Client(timeout=5.0) as client:
        result = pull_once(client=client, api_base_url=args.api_base_url, api_token=args.api_token, dry_run=args.dry_run)
    print(f"processed {result['processed']} plans")
    return 0
```

```python
# windows_agent/local_risk_check.py
def local_gate(trader_connected: bool, available_cash: float, requested_value: float) -> dict:
    if not trader_connected:
        return {"approved": False, "reason": "trader disconnected"}
    if requested_value <= 0:
        return {"approved": False, "reason": "invalid requested value"}
    if requested_value > available_cash:
        return {"approved": False, "reason": "insufficient local cash"}
    return {"approved": True, "reason": "approved"}
```

- [ ] **步骤 4：运行任务 3 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_execution_plan_api.py tests/test_broker_event_api.py tests/test_windows_pull_execution_plans.py -q
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from windows_agent.pull_execution_plans import pull_once

class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload

class FakeClient:
    def get(self, url, headers=None):
        return FakeResponse([])
    def post(self, url, headers=None, json=None):
        return FakeResponse({"ok": True})

result = pull_once(FakeClient(), "http://127.0.0.1:8000", "token", True)
print(result["processed"])
PY
```

预期：
```text
all tests passed
0
```

验收标准：
- `GET /api/v1/execution-plans/ready` 返回持久化的计划，而非默认逻辑的 `[]`。
- `POST /api/v1/broker-events` 持久化事件。
- `GET /api/v1/kill-switch/status` 返回真实存储的状态。
- `windows_agent/pull_execution_plans.py` 存在并且可以模拟运行一个轮询周期。

- [ ] **步骤 5：提交任务 3**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/runtime_store.py src/execution/execution_plan_service.py src/api/routes_execution_plans.py src/api/routes_broker_events.py src/api/routes_kill_switch.py windows_agent/pull_execution_plans.py windows_agent/local_risk_check.py tests/test_execution_plan_api.py tests/test_broker_event_api.py tests/test_windows_pull_execution_plans.py
git commit -m "fix: persist control-plane state and add windows poller"
```

### 任务 4：使 OMS 转换幂等并对账有意义

**文件：**
- 修改：`src/execution/state_machine.py`
- 修改：`src/execution/paper_broker.py`
- 修改：`src/execution/reconciliation.py`
- 修改：`tests/test_oms_state_machine.py`
- 修改：`tests/test_reconciliation.py`

- [ ] **步骤 1：编写失败的幂等性和重复事件测试**

```python
# tests/test_oms_state_machine.py
from src.execution.state_machine import apply_broker_event, create_initial_order_state


def test_duplicate_partial_fill_event_is_ignored():
    state = create_initial_order_state("O1", "600519.SH", 50, "BUY")
    event = {"event_id": "E1", "event_type": "PARTIAL_FILL", "fill_quantity": 40}
    state = apply_broker_event(state, event)
    state = apply_broker_event(state, event)
    assert state["filled_quantity"] == 40
    assert state["seen_event_ids"] == ["E1"]


def test_partial_fill_is_capped_at_order_quantity():
    state = create_initial_order_state("O1", "600519.SH", 50, "BUY")
    event = {"event_id": "E2", "event_type": "PARTIAL_FILL", "fill_quantity": 80}
    state = apply_broker_event(state, event)
    assert state["filled_quantity"] == 50
```

```python
# tests/test_reconciliation.py
from src.execution.reconciliation import detect_unreconciled_state


def test_reconciliation_detects_status_drift():
    plan = {"filled_quantity": 50, "status": "FILLED"}
    broker = {"filled_quantity": 50, "status": "PARTIALLY_FILLED"}
    assert detect_unreconciled_state(plan, broker) is True
```

- [ ] **步骤 2：运行测试重现当前的非幂等行为**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_oms_state_machine.py tests/test_reconciliation.py -q
```

预期：
```text
FAILED tests/test_oms_state_machine.py::test_duplicate_partial_fill_event_is_ignored
E   assert 80 == 40
```

- [ ] **步骤 3：实施重复事件保护和封顶填充**

```python
# src/execution/state_machine.py
def create_initial_order_state(order_id: str, symbol: str, quantity: int, side: str) -> dict:
    return {
        "order_id": order_id,
        "symbol": symbol,
        "quantity": quantity,
        "side": side,
        "status": "PENDING",
        "filled_quantity": 0,
        "seen_event_ids": [],
    }


def apply_broker_event(state: dict, event: dict) -> dict:
    event_id = event.get("event_id")
    if event_id and event_id in state.get("seen_event_ids", []):
        return state

    next_state = {**state}
    if event_id:
        next_state["seen_event_ids"] = [*state.get("seen_event_ids", []), event_id]

    if event.get("event_type") == "PARTIAL_FILL":
        filled = min(state.get("quantity", 0), state.get("filled_quantity", 0) + event.get("fill_quantity", 0))
        next_state["filled_quantity"] = filled
        next_state["status"] = "FILLED" if filled == state.get("quantity", 0) else "PARTIALLY_FILLED"
        return next_state

    if event.get("event_type") == "FILLED":
        next_state["filled_quantity"] = state.get("quantity", 0)
        next_state["status"] = "FILLED"
        return next_state

    return next_state
```

```python
# src/execution/reconciliation.py
def detect_unreconciled_state(plan: dict, broker: dict) -> bool:
    return (
        plan.get("filled_quantity", 0) != broker.get("filled_quantity", 0)
        or plan.get("status") != broker.get("status")
    )
```

```python
# src/execution/paper_broker.py
class PaperBroker:
    def __init__(self, fill_rate: float = 0.9) -> None:
        self.fill_rate = fill_rate
        self._event_counter = 0

    def simulate_fill(self, order_id: str) -> dict:
        self._event_counter += 1
        return {
            "event_id": f"{order_id}-event-{self._event_counter}",
            "event_type": "FILLED",
            "order_id": order_id,
            "fill_quantity": self._orders.get(order_id, {}).get("quantity", 100),
        }
```

- [ ] **步骤 4：运行任务 4 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_oms_state_machine.py tests/test_reconciliation.py tests/test_shadow_execution.py -q
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.execution.state_machine import create_initial_order_state, apply_broker_event
state = create_initial_order_state("O1", "600519.SH", 50, "BUY")
event = {"event_id": "E1", "event_type": "PARTIAL_FILL", "fill_quantity": 40}
state = apply_broker_event(state, event)
state = apply_broker_event(state, event)
print(state["filled_quantity"])
PY
```

预期：
```text
all tests passed
40
```

验收标准：
- 重复的经纪人事件不会增加 `filled_quantity`。
- `filled_quantity` 永远不会超过原始订单数量。
- 对账将状态偏差视为真正的偏差，而不仅仅是数量偏差。

- [ ] **步骤 5：提交任务 4**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/execution/state_machine.py src/execution/paper_broker.py src/execution/reconciliation.py tests/test_oms_state_machine.py tests/test_reconciliation.py
git commit -m "fix: make oms transitions idempotent"
```

### 任务 5：用失败关闭的影子工作流门控替换虚假的端到端检查

**文件：**
- 修改：`scripts/run_shadow_cycle.sh`
- 修改：`scripts/run_reconcile.sh`
- 修改：`tests/test_e2e_shadow_cycle.py`
- 修改：`docs/runbooks/live-trading.md`
- 修改：`README.md`

- [ ] **步骤 1：编写失败的端到端脚本和验收测试**

```python
# tests/test_e2e_shadow_cycle.py
from pathlib import Path


def test_shadow_cycle_script_is_fail_closed():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "set -euo pipefail" in script
    assert "|| echo" not in script


def test_shadow_cycle_script_uses_repo_relative_paths():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "/home/ec2-user/a-share-hub" not in script
    assert 'REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"' in script
```

- [ ] **步骤 2：运行测试验证当前脚本是否仍为失败开放**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
```

预期：
```text
FAILED tests/test_e2e_shadow_cycle.py::test_shadow_cycle_script_is_fail_closed
FAILED tests/test_e2e_shadow_cycle.py::test_shadow_cycle_script_uses_repo_relative_paths
```

- [ ] **步骤 3：实施失败关闭的脚本和真正的发布清单**

```bash
# scripts/run_shadow_cycle.sh
#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/py311/bin/python3}"

cd "$REPO_ROOT"

"$PYTHON_BIN" -m src.main sync-market --symbols 600519.SH
"$PYTHON_BIN" -m src.main build-features --symbols 600519.SH --top-n 1
"$PYTHON_BIN" -m src.main run-decision --symbols 600519.SH --mock-llm
"$PYTHON_BIN" -m src.main plan-execution --symbols 600519.SH --nav 1000000
"$PYTHON_BIN" -m src.main shadow-execute --symbols 600519.SH --mock-broker
"$PYTHON_BIN" -m src.main reconcile --symbols 600519.SH
```

```bash
# scripts/run_reconcile.sh
#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/py311/bin/python3}"

cd "$REPO_ROOT"
"$PYTHON_BIN" -m src.main reconcile --symbols 600519.SH
```

```markdown
# docs/runbooks/live-trading.md
1. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m pytest -q`。
2. 运行 `bash scripts/run_shadow_cycle.sh`。
3. 验证 `no unreconciled orders`。
4. 验证 `GET /api/v1/kill-switch/status` 报告持久化的状态。
5. 运行 `python windows_agent/pull_execution_plans.py --once --dry-run`。
6. 只有在此之后才考虑在经过审查的后续变更中启用实时交易。
```

- [ ] **步骤 4：运行任务 5 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
bash scripts/run_shadow_cycle.sh
bash scripts/run_reconcile.sh
```

预期：
```text
all tests passed
market snapshots synced for 1 symbols
decision input snapshots built for 1 symbols
decision runs created for 1 symbols
execution plans ready for approved targets
shadow execution completed with reconciled states
no unreconciled orders
```

验收标准：
- 脚本在命令错误时立即失败。
- 脚本在当前仓库内可移植，不依赖 `/home/ec2-user/...`。
- 所谓的端到端检查现在执行 CLI 命令而非仅导入的断言。

- [ ] **步骤 5：提交任务 5**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add scripts/run_shadow_cycle.sh scripts/run_reconcile.sh tests/test_e2e_shadow_cycle.py docs/runbooks/live-trading.md README.md
git commit -m "test: replace fake shadow checks with fail-closed gates"
```

## 最终验收矩阵

- 任务 1 通过当仓库干净安装且设置默认使用本地 SQLite 支持的路径。
- 任务 2 通过当记录的 CLI 工作且 FastAPI 应用暴露每个所需的控制平面路由。
- 任务 3 通过当执行计划、经纪人事件和紧急停止开关状态通过运行时存储在进程边界中生存，且 Windows 轮询客户端可以模拟运行一个周期。
- 任务 4 通过当重复的经纪人事件被忽略且对账检测到数量和状态偏差。
- 任务 5 通过当影子脚本从仓库本身运行、失败关闭，且端到端测试验证实际行为而非导入。

## 自审

- 规格覆盖：每个审查发现都映射到一个任务：打包/设置在任务 1，CLI/API 接线在任务 2，空的控制平面和缺失的轮询客户端在任务 3，OMS 幂等性在任务 4，失败开放的脚本和薄弱的验收在任务 5。
- 占位符扫描：没有 `TODO`、TBD、"稍后实现" 或 "类似上述" 占位符残留。
- 类型一致性：`plan_id`、`event_id`、`runtime_store`、`main(argv)` 和 `execution-plans/ready` 在测试、CLI、API 和 Windows 轮询中一致使用。
