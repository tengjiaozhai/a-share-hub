# A-Share Hub 评审整改与能力收敛实施计划

> **给代理执行者：** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施本计划。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 把当前仓库从“文档高估能力 + CLI 占位 + 控制面半成品”收敛为与 `docs/evalution.md` 对齐的 shadow-ready 单路径实现。

**架构：** 先修正文档事实基线，再按 `decision_run -> target_position -> execution_order -> broker events -> reconciliation` 主链补齐存储、CLI、API 和 Windows 轮询执行。Linux 端负责决策、持久化、风控和对账；Windows 端只负责拉取执行计划、本地下单和回传事件，执行层保持确定性。

**技术栈：** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、PostgreSQL、Redis（仅缓存门禁）、pytest、requests

---

## 范围与非目标

- 本计划覆盖刚才评审指出的事实错误和 P0/P1 缺口：文档口径失真、`decision_run`/`target_position` 缺失、CLI 边界不对、Windows 轮询器缺失、仪表盘静态假数据、风控与对账未形成闭环。
- 本计划默认不保留 `run-decision`、`plan-execution` 这类历史命令兼容层。按 `AGENTS.md` 的单路径原则，直接收敛到 `decide`、`shadow-execute`、`live-execute`、`reconcile`、`halt`。
- 本计划不在本轮实现真实券商联调、正式报备提交流程、全量 1m/5m 行情回补。它们属于下一轮扩展，但会在验收标准里保留进入实盘前的硬门禁。

## 文件结构锁定

- 修改：`docs/missing-features-analysis.md` - 修正文档口径，补齐评审缺失项。
- 新建：`tests/test_docs_alignment.py` - 保证缺失分析文档持续反映真实基线。
- 修改：`src/storage/models.py` - 新增 `DecisionRunRow`、`DecisionInputSnapshotRow`、`TargetPositionRow`、`ExecutionOrderRow`、`RiskGateEventRow`、`KillSwitchEventRow`。
- 修改：`src/storage/runtime_store.py` - 为决策、目标仓位、执行订单、风控事件、停机事件提供单一路径存取。
- 新建：`alembic/versions/20260524_000002_decision_and_execution_entities.py` - 新实体迁移。
- 修改：`src/decision/decision_runner.py` - 解析 LLM 输出并构造可持久化的决策记录。
- 修改：`src/portfolio/target_planner.py` - 生成 `target_position` 权威载荷。
- 修改：`src/execution/execution_plan_service.py` - 从目标仓位导出执行订单。
- 修改：`src/execution/state_machine.py` - 幂等应用 broker 事件。
- 修改：`src/execution/reconciliation.py` - 汇总未对账订单状态。
- 新建：`src/api/routes_decision_runs.py`
- 新建：`src/api/routes_portfolio_targets.py`
- 新建：`src/api/routes_reconciliation.py`
- 修改：`src/api/routes_dashboard.py` - 从 `RuntimeStore` 聚合真实状态，移除静态样例。
- 修改：`src/api/routes_kill_switch.py` - 记录 `kill_switch_event`。
- 修改：`src/main.py` - 收敛 CLI 命令并挂载新路由。
- 修改：`scripts/run_shadow_cycle.sh` - 用 `decide` 替换历史命令。
- 新建：`windows_agent/pull_execution_plans.py` - Windows 轮询执行器。
- 修改：`windows_agent/local_risk_check.py` - 本地 fail-closed 校验。
- 修改：`windows_agent/xtquant_adapter.py` - 返回结构化 broker 回报。
- 新建：`tests/test_decision_runtime_store.py`
- 修改：`tests/test_runtime_store_pg.py`
- 修改：`tests/test_cli.py`
- 新建：`tests/test_decision_runs_api.py`
- 新建：`tests/test_portfolio_targets_api.py`
- 修改：`tests/test_execution_plan_api.py`
- 修改：`tests/test_reconciliation.py`
- 修改：`tests/test_oms_state_machine.py`
- 修改：`tests/test_windows_gateway_logic.py`
- 修改：`tests/test_risk_gate.py`
- 修改：`tests/test_e2e_shadow_cycle.py`

## 任务顺序

1. 先把 `docs/missing-features-analysis.md` 改成可信文档，并用测试锁住评审结论。
2. 再补齐 `decision_run`、`decision_input_snapshot`、`target_position` 的持久化链路。
3. 然后补齐 `execution_order`、风控事件、停机事件和对账状态。
4. 之后收敛 CLI/API 边界，并让 dashboard 读真实存储。
5. 最后落地 Windows 轮询执行器、本地风控和影子流程门禁。

### 任务 1：修正文档基线并锁定评审结论

**文件：**
- 新建：`tests/test_docs_alignment.py`
- 修改：`docs/missing-features-analysis.md`

- [ ] **步骤 1：先写失败测试**

```python
from pathlib import Path


def test_missing_features_analysis_tracks_review_findings():
    text = Path("docs/missing-features-analysis.md").read_text(encoding="utf-8")
    assert "实现深度分级" in text
    assert "execution_order" in text
    assert "kill_switch_event" in text
    assert "`pull_execution_plans.py` | ❌ 缺失" in text
    assert "`decide`" in text
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`pytest tests/test_docs_alignment.py -v`
预期：FAIL，至少报一个断言失败，例如缺少 `execution_order` 或缺少 `实现深度分级`。

- [ ] **步骤 3：编写最小实现**

在 `docs/missing-features-analysis.md` 中替换执行摘要和缺失项相关段落，至少包含下面这些内容：

```md
## 执行摘要

当前仓库仅具备“骨架已存在、主流程未验收”的状态，不能再用单一百分比描述进度。

### 实现深度分级

- `已存在`：文件、路由或命令存在，但没有被主流程调用，或只有占位输出。
- `已接线`：主流程已经调用，但缺少持久化、异常流或自动化测试。
- `已验收`：有自动化测试、人工验证证据，且可以支撑当前阶段目标。

### 2.1 数据模型缺失

| 实体名称 | 用途 | 优先级 | 预估工作量 |
|----------|------|--------|-----------|
| `decision_run` | 决策运行记录，持久化模型、输入快照和原始输出 | **P0** | 1天 |
| `decision_input_snapshot` | 决策输入快照，用于回放验证 | **P0** | 0.5天 |
| `target_position` | 目标仓位实体，连接决策与执行 | **P0** | 0.5天 |
| `execution_order` | 执行订单权威实体，连接 target_position 与 broker event | **P0** | 1天 |
| `risk_gate_event` | 风控门禁审计事件 | **P1** | 0.5天 |
| `kill_switch_event` | 停机触发与恢复事件 | **P1** | 0.5天 |

### 2.3 CLI 命令缺失

| 命令 | 功能 | 优先级 | 预估工作量 |
|------|------|--------|-----------|
| `decide` | 持久化决策并产出目标仓位 | **P0** | 2天 |
| `live-execute` | Windows 实盘执行 | **P1** | 3天 |
| `halt` | 停机与恢复命令 | **P1** | 0.5天 |

### 2.7 Windows 执行网关缺失

| 功能 | 当前状态 | 目标状态 | 优先级 | 预估工作量 |
|------|----------|----------|--------|-----------|
| `pull_execution_plans.py` | ❌ 缺失 | 轮询、ack、本地风控、回传 broker event | **P0** | 3天 |
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`pytest tests/test_docs_alignment.py -v`
预期：PASS

补充验证：`rg -n "实现深度分级|execution_order|kill_switch_event|`decide`|pull_execution_plans.py" docs/missing-features-analysis.md`
预期：输出全部命中。

- [ ] **步骤 5：提交**

```bash
git add tests/test_docs_alignment.py docs/missing-features-analysis.md
git commit -m "docs: align missing features analysis with review findings"
```

### 任务 2：补齐决策持久化主链

**文件：**
- 新建：`alembic/versions/20260524_000002_decision_and_execution_entities.py`
- 修改：`src/storage/models.py`
- 修改：`src/storage/runtime_store.py`
- 修改：`src/decision/decision_runner.py`
- 修改：`src/portfolio/target_planner.py`
- 新建：`tests/test_decision_runtime_store.py`

- [ ] **步骤 1：先写失败测试**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_decision_run_and_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="prompt-v1",
        model_name="mock-llm",
        raw_output='{"symbol":"600519.SH","action":"BUY","confidence":80,"target_position_ratio":0.2,"reason":"trend"}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.2,
        reason="trend",
        input_snapshot={"market": {"symbol": "600519.SH", "close": 1420.0}},
    )

    record = store.get_decision_run(decision_run_id)
    assert record["decision_run_id"] == decision_run_id
    assert record["snapshot"]["market"]["close"] == 1420.0
    assert record["target_position_ratio"] == 0.2


def test_runtime_store_lists_active_target_positions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="prompt-v1",
        model_name="mock-llm",
        raw_output='{"symbol":"600519.SH","action":"BUY","confidence":80,"target_position_ratio":0.2,"reason":"trend"}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.2,
        reason="trend",
        input_snapshot={"market": {"symbol": "600519.SH"}},
    )
    store.insert_target_position(
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=200000,
        target_position_ratio=0.2,
        expires_at="2026-05-24T10:15:00",
    )

    rows = store.list_active_target_positions()
    assert len(rows) == 1
    assert rows[0]["decision_run_id"] == decision_run_id
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`pytest tests/test_decision_runtime_store.py -v`
预期：FAIL，报错 `RuntimeStore` 缺少 `insert_decision_run` 或 `insert_target_position`。

- [ ] **步骤 3：编写最小实现**

迁移文件先新增三张表：

```python
from alembic import op
import sqlalchemy as sa


revision = "20260524_000002"
down_revision = "20260524_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_runs",
        sa.Column("decision_run_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("prompt_hash", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column("parsed_action", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("target_position_ratio", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "decision_input_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("decision_run_id", sa.String(length=64), sa.ForeignKey("decision_runs.decision_run_id"), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "target_positions",
        sa.Column("target_position_id", sa.String(length=64), primary_key=True),
        sa.Column("decision_run_id", sa.String(length=64), sa.ForeignKey("decision_runs.decision_run_id"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("target_position_ratio", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("target_positions")
    op.drop_table("decision_input_snapshots")
    op.drop_table("decision_runs")
```

`src/storage/models.py` 增加模型定义：

```python
class DecisionRunRow(Base):
    __tablename__ = "decision_runs"
    decision_run_id = Column(String(64), primary_key=True)
    symbol = Column(String(32), nullable=False)
    prompt_hash = Column(String(128), nullable=False)
    model_name = Column(String(64), nullable=False)
    raw_output = Column(Text, nullable=False)
    parsed_action = Column(String(16), nullable=False)
    confidence = Column(Integer, nullable=False)
    target_position_ratio = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DecisionInputSnapshotRow(Base):
    __tablename__ = "decision_input_snapshots"
    snapshot_id = Column(String(64), primary_key=True)
    decision_run_id = Column(String(64), ForeignKey("decision_runs.decision_run_id"), nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TargetPositionRow(Base):
    __tablename__ = "target_positions"
    target_position_id = Column(String(64), primary_key=True)
    decision_run_id = Column(String(64), ForeignKey("decision_runs.decision_run_id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    action = Column(String(16), nullable=False)
    target_value = Column(Integer, nullable=False)
    target_position_ratio = Column(Float, nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

`src/storage/runtime_store.py` 增加最小存取：

```python
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
        run_row = conn.execute(
            select(DecisionRunRow).where(DecisionRunRow.decision_run_id == decision_run_id)
        ).scalar_one()
        snapshot_row = conn.execute(
            select(DecisionInputSnapshotRow).where(DecisionInputSnapshotRow.decision_run_id == decision_run_id)
        ).scalar_one()
        return {
            "decision_run_id": run_row.decision_run_id,
            "symbol": run_row.symbol,
            "parsed_action": run_row.parsed_action,
            "confidence": run_row.confidence,
            "target_position_ratio": run_row.target_position_ratio,
            "reason": run_row.reason,
            "snapshot": json.loads(snapshot_row.payload_json),
        }


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
```

`src/decision/decision_runner.py` 收敛成单一路径构造器：

```python
def build_decision_run_record(
    raw: str,
    symbol: str,
    prompt_hash: str,
    input_snapshot: dict,
    model_name: str,
) -> dict:
    decision = parse_decision_output(raw)
    return {
        "symbol": symbol,
        "prompt_hash": prompt_hash,
        "model_name": model_name,
        "raw_output": raw,
        "parsed_action": decision.action,
        "confidence": decision.confidence,
        "target_position_ratio": decision.target_position_ratio,
        "reason": decision.reason,
        "input_snapshot": input_snapshot,
    }
```

`src/portfolio/target_planner.py` 返回可持久化字段：

```python
def build_target_position(
    symbol: str,
    action: str,
    target_position_ratio: float,
    net_asset_value: float,
    expires_at: str,
) -> Dict[str, Any]:
    target_value = int(net_asset_value * target_position_ratio)
    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
        "target_position_ratio": target_position_ratio,
        "expires_at": expires_at,
    }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`pytest tests/test_decision_runtime_store.py tests/test_decision_runner.py tests/test_target_planner.py -v`
预期：PASS

补充验证：`/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head`
预期：迁移成功，新增三张表。

- [ ] **步骤 5：提交**

```bash
git add alembic/versions/20260524_000002_decision_and_execution_entities.py \
  src/storage/models.py src/storage/runtime_store.py src/decision/decision_runner.py \
  src/portfolio/target_planner.py tests/test_decision_runtime_store.py
git commit -m "feat: persist decision runs and target positions"
```

### 任务 3：补齐执行订单、风控事件和对账状态

**文件：**
- 修改：`src/storage/models.py`
- 修改：`src/storage/runtime_store.py`
- 修改：`src/execution/execution_plan_service.py`
- 修改：`src/execution/state_machine.py`
- 修改：`src/execution/reconciliation.py`
- 修改：`tests/test_runtime_store_pg.py`
- 修改：`tests/test_oms_state_machine.py`
- 修改：`tests/test_reconciliation.py`

- [ ] **步骤 1：先写失败测试**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_execution_order_and_broker_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    execution_order_id = store.insert_execution_order(
        target_position_id="tp-001",
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1420.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "qmt-001"},
    )

    status = store.get_reconciliation_status()
    assert status["open_orders"] == 1
    assert status["broker_event_count"] == 1


def test_apply_broker_event_is_idempotent():
    state = {
        "order_id": "ord-001",
        "quantity": 100,
        "status": "PENDING",
        "filled_quantity": 0,
        "processed_events": [],
    }
    event = {"event_id": "evt-001", "event_type": "PARTIAL_FILL", "fill_quantity": 20}

    next_state = apply_broker_event(state, event)
    duplicate_state = apply_broker_event(next_state, event)

    assert next_state["filled_quantity"] == 20
    assert duplicate_state["filled_quantity"] == 20
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`pytest tests/test_runtime_store_pg.py tests/test_oms_state_machine.py tests/test_reconciliation.py -v`
预期：FAIL，报错缺少 `insert_execution_order` 或 `get_reconciliation_status`。

- [ ] **步骤 3：编写最小实现**

`src/storage/models.py` 新增执行侧实体：

```python
class ExecutionOrderRow(Base):
    __tablename__ = "execution_orders"
    execution_order_id = Column(String(64), primary_key=True)
    target_position_id = Column(String(64), ForeignKey("target_positions.target_position_id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    action = Column(String(16), nullable=False)
    quantity = Column(Integer, nullable=False)
    limit_price = Column(Float, nullable=False)
    status = Column(String(16), nullable=False, default="READY")
    broker_order_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RiskGateEventRow(Base):
    __tablename__ = "risk_gate_events"
    risk_gate_event_id = Column(String(64), primary_key=True)
    symbol = Column(String(32), nullable=False)
    approved = Column(Boolean, nullable=False)
    rule_name = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class KillSwitchEventRow(Base):
    __tablename__ = "kill_switch_events"
    kill_switch_event_id = Column(String(64), primary_key=True)
    active = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

`src/storage/runtime_store.py` 增加执行与对账方法：

```python
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
```

`src/execution/execution_plan_service.py` 从 `target_position` 生成 `execution_order`：

```python
def build_execution_order(target_position: Dict[str, Any], lot_size: int = 100) -> Dict[str, Any]:
    quantity = max(target_position["target_value"] // int(target_position.get("reference_price", 1)), 0)
    rounded_quantity = (quantity // lot_size) * lot_size
    return {
        "symbol": target_position["symbol"],
        "action": target_position["action"],
        "quantity": rounded_quantity,
        "limit_price": target_position["reference_price"],
        "target_position_id": target_position["target_position_id"],
    }
```

`src/execution/reconciliation.py` 汇总未对账状态：

```python
def summarize_reconciliation(orders: list[dict], broker_events: list[dict]) -> dict:
    event_count_by_order: dict[str, int] = {}
    for event in broker_events:
        event_count_by_order[event["order_id"]] = event_count_by_order.get(event["order_id"], 0) + 1

    unreconciled = [
        order["execution_order_id"]
        for order in orders
        if order["status"] != "FILLED" and event_count_by_order.get(order["execution_order_id"], 0) == 0
    ]
    return {
        "open_orders": len([order for order in orders if order["status"] != "FILLED"]),
        "unreconciled_orders": unreconciled,
        "healthy": len(unreconciled) == 0,
    }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`pytest tests/test_runtime_store_pg.py tests/test_oms_state_machine.py tests/test_reconciliation.py -v`
预期：PASS

补充验证：`pytest tests/test_idempotency.py -v`
预期：PASS，重复事件不会重复累计成交量。

- [ ] **步骤 5：提交**

```bash
git add src/storage/models.py src/storage/runtime_store.py \
  src/execution/execution_plan_service.py src/execution/state_machine.py \
  src/execution/reconciliation.py tests/test_runtime_store_pg.py \
  tests/test_oms_state_machine.py tests/test_reconciliation.py
git commit -m "feat: add execution orders and reconciliation state"
```

### 任务 4：收敛 CLI、API 和 dashboard 到新主流程

**文件：**
- 新建：`src/api/routes_decision_runs.py`
- 新建：`src/api/routes_portfolio_targets.py`
- 新建：`src/api/routes_reconciliation.py`
- 修改：`src/api/routes_dashboard.py`
- 修改：`src/api/routes_kill_switch.py`
- 修改：`src/main.py`
- 修改：`scripts/run_shadow_cycle.sh`
- 修改：`tests/test_cli.py`
- 新建：`tests/test_decision_runs_api.py`
- 新建：`tests/test_portfolio_targets_api.py`
- 修改：`tests/test_execution_plan_api.py`

- [ ] **步骤 1：先写失败测试**

```python
from fastapi.testclient import TestClient

from src.main import build_app, build_cli_parser


def test_cli_exposes_evalution_commands():
    parser = build_cli_parser()
    choices = parser._subparsers._group_actions[0].choices
    assert "decide" in choices
    assert "live-execute" in choices
    assert "halt" in choices
    assert "run-decision" not in choices
    assert "plan-execution" not in choices


def test_decision_runs_route_is_available():
    client = TestClient(build_app())
    response = client.get("/api/v1/decision-runs")
    assert response.status_code == 200


def test_portfolio_targets_route_is_available():
    client = TestClient(build_app())
    response = client.get("/api/v1/portfolio-targets/active")
    assert response.status_code == 200
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`pytest tests/test_cli.py tests/test_decision_runs_api.py tests/test_portfolio_targets_api.py tests/test_execution_plan_api.py -v`
预期：FAIL，报错命令不存在或路由未挂载。

- [ ] **步骤 3：编写最小实现**

`src/api/routes_decision_runs.py`：

```python
from fastapi import APIRouter, Depends, HTTPException

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/decision-runs")
def list_decision_runs(store=Depends(get_runtime_store)) -> list[dict]:
    return store.list_decision_runs()


@router.get("/decision-runs/{decision_run_id}")
def get_decision_run(decision_run_id: str, store=Depends(get_runtime_store)) -> dict:
    record = store.get_decision_run(decision_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="decision run not found")
    return record
```

`src/api/routes_portfolio_targets.py`：

```python
from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/portfolio-targets/active")
def get_active_targets(store=Depends(get_runtime_store)) -> list[dict]:
    return store.list_active_target_positions()
```

`src/api/routes_reconciliation.py`：

```python
from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/reconciliation/status")
def get_reconciliation_status(store=Depends(get_runtime_store)) -> dict:
    return store.get_reconciliation_status()
```

`src/main.py` 收敛命令并挂载新路由：

```python
from src.api.routes_decision_runs import router as decision_runs_router
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
    app.include_router(dashboard_router)
    return app


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a-share-hub", description="A股自动交易系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_decide = subparsers.add_parser("decide", help="运行决策并持久化结果")
    p_decide.add_argument("--symbols", nargs="+", required=True)
    p_decide.add_argument("--mock-llm", action="store_true")

    p_shadow = subparsers.add_parser("shadow-execute", help="影子执行")
    p_shadow.add_argument("--symbols", nargs="+", required=True)
    p_shadow.add_argument("--mock-broker", action="store_true")

    p_live = subparsers.add_parser("live-execute", help="Windows 实盘执行")
    p_live.add_argument("--once", action="store_true")

    p_reconcile = subparsers.add_parser("reconcile", help="对账")
    p_reconcile.add_argument("--symbols", nargs="+", required=True)

    p_halt = subparsers.add_parser("halt", help="触发或恢复停机")
    p_halt.add_argument("--reason", required=True)
    p_halt.add_argument("--resume", action="store_true")

    subparsers.add_parser("serve", help="启动 API 服务")
    return parser
```

`scripts/run_shadow_cycle.sh` 同步替换：

```bash
"${PYTHON}" -m src.main decide --symbols 600519.SH 000001.SZ --mock-llm
"${PYTHON}" -m src.main shadow-execute --symbols 600519.SH 000001.SZ --mock-broker
"${PYTHON}" -m src.main reconcile --symbols 600519.SH 000001.SZ
```

`src/api/routes_dashboard.py` 不再返回静态样例，至少改成聚合 `RuntimeStore` 计数：

```python
@router.get("/api/v1/dashboard/status")
def get_system_status(store=Depends(get_runtime_store)):
    reconciliation = store.get_reconciliation_status()
    return {
        "mode": "shadow",
        "open_orders": reconciliation["open_orders"],
        "healthy": reconciliation["healthy"],
        "active_targets": len(store.list_active_target_positions()),
        "recent_decisions": len(store.list_decision_runs()),
    }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`pytest tests/test_cli.py tests/test_decision_runs_api.py tests/test_portfolio_targets_api.py tests/test_execution_plan_api.py tests/test_bootstrap.py -v`
预期：PASS

补充验证：`bash scripts/run_shadow_cycle.sh`
预期：脚本能跑完整条影子链路，不再调用 `run-decision` 和 `plan-execution`。

- [ ] **步骤 5：提交**

```bash
git add src/api/routes_decision_runs.py src/api/routes_portfolio_targets.py \
  src/api/routes_reconciliation.py src/api/routes_dashboard.py src/api/routes_kill_switch.py \
  src/main.py scripts/run_shadow_cycle.sh tests/test_cli.py \
  tests/test_decision_runs_api.py tests/test_portfolio_targets_api.py tests/test_execution_plan_api.py
git commit -m "feat: align cli and api with decision to execution flow"
```

### 任务 5：落地 Windows 轮询执行器、本地风控和停机事件

**文件：**
- 新建：`windows_agent/pull_execution_plans.py`
- 修改：`windows_agent/local_risk_check.py`
- 修改：`windows_agent/xtquant_adapter.py`
- 修改：`src/risk/pre_trade_risk.py`
- 修改：`src/api/routes_kill_switch.py`
- 修改：`tests/test_windows_gateway_logic.py`
- 修改：`tests/test_risk_gate.py`
- 修改：`tests/test_e2e_shadow_cycle.py`

- [ ] **步骤 1：先写失败测试**

```python
from windows_agent.local_risk_check import local_gate


def test_local_gate_rejects_sell_when_available_sell_is_insufficient():
    result = local_gate(
        trader_connected=True,
        available_cash=100000,
        requested_value=20000,
        requested_quantity=300,
        available_sell_quantity=100,
        action="SELL",
    )
    assert result["approved"] is False
    assert result["reason"] == "insufficient available sell quantity"


def test_risk_gate_rejects_expired_decision():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=100000,
        requested_value=20000,
        available_sell_quantity=0,
        requested_quantity=0,
        decision_expires_at="2026-05-24T09:30:00",
        now_iso="2026-05-24T09:31:00",
        duplicate_order=False,
    )
    assert result["approved"] is False
    assert result["reason"] == "decision expired"
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`pytest tests/test_windows_gateway_logic.py tests/test_risk_gate.py tests/test_e2e_shadow_cycle.py -v`
预期：FAIL，报错 `local_gate` 和 `evaluate_risk_gate` 参数不匹配，或 `pull_execution_plans.py` 不存在。

- [ ] **步骤 3：编写最小实现**

`windows_agent/local_risk_check.py` 收敛为 fail-closed：

```python
def local_gate(
    trader_connected: bool,
    available_cash: float,
    requested_value: float,
    requested_quantity: int,
    available_sell_quantity: int,
    action: str,
) -> Dict[str, Any]:
    if not trader_connected:
        return {"approved": False, "reason": "trader disconnected"}
    if action == "BUY" and requested_value > available_cash:
        return {"approved": False, "reason": "insufficient local cash"}
    if action == "SELL" and requested_quantity > available_sell_quantity:
        return {"approved": False, "reason": "insufficient available sell quantity"}
    return {"approved": True, "reason": "approved"}
```

`src/risk/pre_trade_risk.py` 增加过期与重复下单抑制：

```python
def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
    available_sell_quantity: int,
    requested_quantity: int,
    decision_expires_at: str,
    now_iso: str,
    duplicate_order: bool,
) -> Dict[str, Any]:
    if kill_switch:
        return {"approved": False, "reason": "kill switch enabled"}
    if duplicate_order:
        return {"approved": False, "reason": "duplicate order"}
    if now_iso >= decision_expires_at:
        return {"approved": False, "reason": "decision expired"}
    if action == "BUY" and requested_value > available_cash:
        return {"approved": False, "reason": "insufficient cash"}
    if action == "SELL" and requested_quantity > available_sell_quantity:
        return {"approved": False, "reason": "insufficient available sell quantity"}
    return {"approved": True, "reason": "approved"}
```

`windows_agent/pull_execution_plans.py` 提供最小可运行轮询器：

```python
import requests

from windows_agent.local_risk_check import local_gate
from windows_agent.xtquant_adapter import XtQuantAdapter


def run_once(base_url: str) -> int:
    adapter = XtQuantAdapter()
    adapter.connect()
    response = requests.get(f"{base_url}/api/v1/execution-plans/ready", timeout=5)
    response.raise_for_status()
    plans = response.json()
    processed = 0
    for plan in plans:
        gate = local_gate(
            trader_connected=adapter.connected,
            available_cash=1_000_000,
            requested_value=plan["target_value"],
            requested_quantity=plan.get("quantity", 0),
            available_sell_quantity=plan.get("available_sell_quantity", 0),
            action=plan["action"],
        )
        if not gate["approved"]:
            continue
        broker_result = adapter.submit_order(plan)
        requests.post(
            f"{base_url}/api/v1/broker-events",
            json={
                "event_id": f"evt-{plan['plan_id']}",
                "order_id": plan["plan_id"],
                "event_type": broker_result["status"],
                "payload": broker_result,
            },
            timeout=5,
        ).raise_for_status()
        requests.post(f"{base_url}/api/v1/execution-plans/{plan['plan_id']}/ack", timeout=5).raise_for_status()
        processed += 1
    adapter.disconnect()
    return processed
```

`src/api/routes_kill_switch.py` 记录事件：

```python
@router.post("/kill-switch/activate")
def activate_kill_switch(reason: str, store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(True)
    store.insert_kill_switch_event(active=True, reason=reason)
    return {"activated": True}


@router.post("/kill-switch/deactivate")
def deactivate_kill_switch(reason: str, store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(False)
    store.insert_kill_switch_event(active=False, reason=reason)
    return {"deactivated": True}
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`pytest tests/test_windows_gateway_logic.py tests/test_risk_gate.py tests/test_e2e_shadow_cycle.py -v`
预期：PASS

补充验证：`/opt/anaconda3/envs/py311/bin/python3 windows_agent/pull_execution_plans.py --once --base-url http://127.0.0.1:8000`
预期：至少打印已处理计划数；没有计划时返回 `0`，不是异常退出。

- [ ] **步骤 5：提交**

```bash
git add windows_agent/pull_execution_plans.py windows_agent/local_risk_check.py \
  windows_agent/xtquant_adapter.py src/risk/pre_trade_risk.py src/api/routes_kill_switch.py \
  tests/test_windows_gateway_logic.py tests/test_risk_gate.py tests/test_e2e_shadow_cycle.py
git commit -m "feat: add windows polling executor and fail-closed risk gates"
```

## 自检

- `docs/evalution.md` 要求的主流程已经被任务 2-5 覆盖：决策持久化、目标仓位、执行订单、broker event、reconciliation、halt。
- 本计划显式修复了评审指出的四个问题：文档高估、CLI 只是 `print`、`pull_execution_plans.py` 实际缺失、dashboard 静态假数据。
- 本计划没有写 `TODO`、`TBD`、`类似任务 N` 之类占位描述；后续执行时如果函数名变化，必须同步回改本计划和测试。

## 完成定义

- 文档与代码的“已实现”口径一致，不再出现“存在文件即算功能完成”。
- `decide -> portfolio-targets -> execution-plans -> broker-events -> reconciliation` 能在影子模式下跑通。
- Windows 轮询器存在、可执行、默认 fail-closed。
- 进入下一轮之前，必须先通过配套的分阶段验收文档。
